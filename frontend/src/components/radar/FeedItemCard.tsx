import { Bookmark, BookmarkCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { radarControlSizes } from "@/pages/radar-ui-config";
import { parseSummary, stripHtml } from "./feed-summary";
import type { FeedItem } from "@/api/client";

interface Props {
  item: FeedItem;
  bookmarked: boolean;
  canBookmark: boolean;
  onToggleBookmark: (item: FeedItem) => void;
  onOpen: (item: FeedItem) => void;
}

function formatItemTime(iso: string) {
  const value = new Date(iso);
  const sameDay = value.toDateString() === new Date().toDateString();
  const time = value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return sameDay ? time : `${value.toLocaleDateString([], { month: "2-digit", day: "2-digit" })} ${time}`;
}

export default function FeedItemCard({ item, bookmarked, canBookmark, onToggleBookmark, onOpen }: Props) {
  const { t } = useTranslation();
  const symbols = item.symbols.slice(0, 2);
  const time = item.published_at ?? item.fetched_at;
  const { text: summaryText, images } = item.summary
    ? parseSummary(item.summary)
    : { text: "", images: [] };
  const thumbnail = images[0] ?? null;

  return (
    <Card
      onClick={() => onOpen(item)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(item);
        }
      }}
      className={cn(
        "group cursor-pointer gap-0 overflow-hidden rounded-none border-0 border-b border-[var(--data-grid-line)] bg-transparent p-0 shadow-none last:border-b-0",
        "transition-colors duration-150 hover:bg-muted/35",
      )}
    >
      <CardContent className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 p-3">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-micro uppercase tracking-wide text-muted-foreground">
            <span className="market-data-value font-semibold text-[var(--market-info)]">
              {formatItemTime(time)}
            </span>
            <span>·</span>
            <span className="font-medium text-foreground">
            {item.source_key}
            </span>
            <span>·</span>
            <span>{t(`radar.category.${item.category}`, item.category)}</span>
            {symbols.map((symbol) => (
              <span
                key={symbol}
                className="market-data-value rounded-[4px] border border-[var(--data-grid-line)] bg-muted/40 px-1.5 py-0.5 text-[var(--market-warning)]"
              >
                {item.symbol_labels?.[symbol] ?? symbol}
              </span>
            ))}
          </div>

          <div
            className={cn(
              "font-semibold leading-snug text-foreground transition-colors group-hover:text-[var(--accent)]",
              radarControlSizes.bodyTextClassName,
            )}
          >
            {stripHtml(item.title)}
          </div>

          {summaryText ? (
            <p className={cn("mt-1 line-clamp-2 leading-relaxed text-muted-foreground", radarControlSizes.metaTextClassName)}>
              {summaryText}
            </p>
          ) : null}
        </div>

        <div className="flex items-start gap-2">
          {thumbnail ? (
            <img
              src={thumbnail}
              alt=""
              loading="lazy"
              className="hidden h-16 w-24 rounded-[6px] border border-[var(--data-grid-line)] object-cover sm:block"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          ) : null}
          {canBookmark ? (
            <Button
              type="button"
              variant="ghost"
              size={radarControlSizes.bookmarkAction}
              className={cn("text-muted-foreground", bookmarked && "text-[var(--accent)]")}
              onClick={(e) => {
                e.stopPropagation();
                onToggleBookmark(item);
              }}
              title={bookmarked ? t("radar.unbookmark") : t("radar.bookmark")}
            >
              {bookmarked ? <BookmarkCheck strokeWidth={1.8} /> : <Bookmark strokeWidth={1.8} />}
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
