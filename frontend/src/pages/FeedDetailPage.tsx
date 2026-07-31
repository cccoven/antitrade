import { useEffect, useState, useCallback } from "react";
import { useLocation, useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, Bookmark, BookmarkCheck, ExternalLink } from "lucide-react";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import FlushPage from "@/components/FlushPage";
import { cn } from "@/lib/utils";
import { radarControlSizes } from "./radar-ui-config";
import { parseSummary, resolveFeedUrl, stripHtml } from "@/components/radar/feed-summary";
import { openExternal } from "@/lib/open-external";
import { useAuth } from "@/auth/auth-context";
import {
  type FeedItem, type FeedBookmark,
  getFeedItem, listFeedBookmarks, addFeedBookmark, removeFeedBookmark,
} from "@/api/client";

const controlStyle = { fontSize: radarControlSizes.fontSize, fontWeight: radarControlSizes.fontWeight };

export default function FeedDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { user } = useAuth();

  const [item, setItem] = useState<FeedItem | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [bookmark, setBookmark] = useState<FeedBookmark | null>(null);
  const requestedReturnTo = (location.state as { from?: unknown } | null)?.from;
  const returnTo = typeof requestedReturnTo === "string"
    && requestedReturnTo.startsWith("/")
    && !requestedReturnTo.startsWith("//")
    ? requestedReturnTo
    : "/radar";

  useEffect(() => {
    let cancelled = false;
    getFeedItem(id)
      .then((it) => { if (!cancelled) setItem(it); })
      .catch(() => { if (!cancelled) setNotFound(true); });
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    if (!user) { setBookmark(null); return; }
    listFeedBookmarks()
      .then((bms) => setBookmark(bms.find((b) => b.feed_item_id === id) ?? null))
      .catch(() => setBookmark(null));
  }, [user, id]);

  const toggleBookmark = useCallback(async () => {
    if (!item) return;
    try {
      if (bookmark) {
        await removeFeedBookmark(bookmark.id);
        setBookmark(null);
      } else {
        setBookmark(await addFeedBookmark(item.id));
      }
    } catch { /* toast handled upstream */ }
  }, [item, bookmark]);

  const back = (
    <TooltipIconButton
      label={t("radar.back")}
      variant="ghost"
      size={radarControlSizes.iconAction}
      style={controlStyle}
      onClick={() => navigate(returnTo)}
    >
      <ChevronLeft />
    </TooltipIconButton>
  );

  if (notFound) {
    return (
      <FlushPage toolbar={back}>
        <p className={cn("text-muted-foreground", radarControlSizes.metaTextClassName)}>
          {t("radar.notFound")}
        </p>
      </FlushPage>
    );
  }
  if (!item) {
    return (
      <FlushPage toolbar={back}>
        <p className={cn("text-muted-foreground", radarControlSizes.metaTextClassName)}>
          {t("radar.loading")}
        </p>
      </FlushPage>
    );
  }

  const { paragraphs, images } = item.summary ? parseSummary(item.summary) : { paragraphs: [], images: [] };
  const time = item.published_at ?? item.fetched_at;
  const externalUrl = resolveFeedUrl(item.url);

  return (
    <FlushPage
      toolbar={back}
      toolbarAside={
        <div className="flex items-center gap-2">
          {user ? (
            <TooltipIconButton
              label={bookmark ? t("radar.unbookmark") : t("radar.bookmark")}
              variant="outline"
              size={radarControlSizes.iconAction}
              style={controlStyle}
              className={cn(bookmark && "text-[var(--accent)] border-[var(--accent-strong)]")}
              onClick={toggleBookmark}
            >
              {bookmark ? <BookmarkCheck /> : <Bookmark />}
            </TooltipIconButton>
          ) : null}
          {externalUrl ? (
            <TooltipIconButton
              label={t("radar.openOriginal")}
              variant="default"
              size={radarControlSizes.iconAction}
              style={controlStyle}
              onClick={() => openExternal(externalUrl)}
            >
              <ExternalLink />
            </TooltipIconButton>
          ) : null}
        </div>
      }
    >
      <article className="mx-auto flex w-full max-w-3xl flex-col gap-5 pt-2">
        <div className="flex flex-col gap-3">
          <h1 className="text-heading font-semibold leading-snug tracking-[0.01em] text-foreground">{stripHtml(item.title)}</h1>
          <div className={cn("flex flex-wrap items-center gap-x-2.5 gap-y-1 tracking-[0.02em] text-muted-foreground", radarControlSizes.metaTextClassName)}>
            <span>{item.source_key}</span>
            <span>· {new Date(time).toLocaleString()}</span>
            <span>· {t(`radar.category.${item.category}`, item.category)}</span>
          </div>
          {item.symbols.length ? (
            <div className="flex flex-wrap gap-1.5">
              {item.symbols.map((s) => (
                <span
                  key={s}
                  className={cn(
                    "inline-flex items-center rounded-md border border-[var(--accent-strong)] bg-[var(--accent-soft)] px-2 py-0.5 font-normal tracking-[0.02em] text-[var(--accent)]",
                    radarControlSizes.metaTextClassName,
                  )}
                >
                  {item.symbol_labels?.[s] ?? s}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {images.length > 0 ? (
          <div className="flex flex-col gap-3">
            {images.map((src) => (
              <img
                key={src}
                src={src}
                alt=""
                loading="lazy"
                className="w-full rounded-lg border border-border object-contain"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
              />
            ))}
          </div>
        ) : null}

        {paragraphs.length > 0 ? (
          <div className="flex flex-col gap-4">
            {paragraphs.map((para, i) => (
              <p
                key={i}
                className="text-foreground/90"
                style={{ fontSize: "15px", lineHeight: 2, letterSpacing: "0.03em" }}
              >
                {para}
              </p>
            ))}
          </div>
        ) : (
          <p className={cn("text-muted-foreground", radarControlSizes.bodyTextClassName)}>
            {t("radar.noContent")}
          </p>
        )}
      </article>
    </FlushPage>
  );
}
