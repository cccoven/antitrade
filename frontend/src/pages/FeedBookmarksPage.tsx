import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft } from "lucide-react";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import FlushPage from "@/components/FlushPage";
import FeedItemCard from "@/components/radar/FeedItemCard";
import { radarControlSizes } from "./radar-ui-config";
import {
  type FeedBookmarkItem,
  listFeedBookmarkItems, removeFeedBookmark,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";

const controlStyle = { fontSize: radarControlSizes.fontSize, fontWeight: radarControlSizes.fontWeight };
const PAGE_SIZE = 20;

export default function FeedBookmarksPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<FeedBookmarkItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    listFeedBookmarkItems({ page: 1, page_size: PAGE_SIZE })
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
        setTotal(r.total);
      })
      .catch(() => { if (!cancelled) { setItems([]); setTotal(0); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user]);

  const loadMore = useCallback(() => {
    if (loading || items.length >= total) return;
    // Derive the page from how many rows we already hold (not a counter), and
    // dedupe on append — un-bookmarking removes rows locally, so a fixed page
    // counter would drift out of sync with the (also shrinking) server list.
    const nextPage = Math.floor(items.length / PAGE_SIZE) + 1;
    setLoading(true);
    listFeedBookmarkItems({ page: nextPage, page_size: PAGE_SIZE })
      .then((r) => {
        setItems((cur) => {
          const seen = new Set(cur.map((it) => it.id));
          return [...cur, ...r.items.filter((it) => !seen.has(it.id))];
        });
        setTotal(r.total);
      })
      .catch(() => { /* toast handled upstream */ })
      .finally(() => setLoading(false));
  }, [loading, items.length, total]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => { if (entries[0]?.isIntersecting) loadMore(); },
      { rootMargin: "400px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore]);

  const handleUnbookmark = useCallback(async (item: FeedBookmarkItem) => {
    try {
      await removeFeedBookmark(item.bookmark_id);
      setItems((cur) => cur.filter((it) => it.id !== item.id));
      setTotal((n) => Math.max(0, n - 1));
    } catch {
      // unwrapResponse already surfaced a toast; keep the row on failure.
    }
  }, []);

  const back = (
    <TooltipIconButton
      label={t("radar.back")}
      variant="ghost"
      size={radarControlSizes.iconAction}
      style={controlStyle}
      onClick={() => navigate("/radar")}
    >
      <ChevronLeft />
    </TooltipIconButton>
  );

  const toolbar = (
    <div className="flex items-center gap-3">
      {back}
      <span className={radarControlSizes.titleTextClassName}>{t("radar.myBookmarks")}</span>
    </div>
  );

  if (!user) {
    return (
      <FlushPage toolbar={toolbar}>
        <p className={`text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
          {t("radar.bookmarksSignIn")}
        </p>
      </FlushPage>
    );
  }

  return (
    <FlushPage
      toolbar={toolbar}
    >
      {items.length === 0 && !loading ? (
        <p className={`text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
          {t("radar.bookmarksEmpty")}
        </p>
      ) : (
        <section className="overflow-hidden rounded-[var(--radius-data-panel)] border border-[var(--data-grid-line)] bg-[var(--data-panel-bg)]">
          {items.map((item) => (
            <FeedItemCard
              key={item.id}
              item={item}
              bookmarked={true}
              canBookmark={true}
              onToggleBookmark={() => handleUnbookmark(item)}
              onOpen={(it) => navigate(`/radar/${it.id}`)}
            />
          ))}
          <div ref={sentinelRef} className="h-px" />
          {loading ? (
            <p className={`py-3 text-center text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
              {t("radar.loading")}
            </p>
          ) : items.length >= total && total > 0 ? (
            <p className={`py-3 text-center text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
              {t("radar.end")}
            </p>
          ) : null}
        </section>
      )}
    </FlushPage>
  );
}
