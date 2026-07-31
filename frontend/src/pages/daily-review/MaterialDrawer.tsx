import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dailyReviewControlStyle } from "@/pages/daily-review-ui-config";
import { authedAssetUrl, type Trade, type TradeImage, type TradeStats } from "@/api/client";
import { cn } from "@/lib/utils";
import { useJournalSettings } from "@/journal/journal-settings-context";

export interface MaterialDrawerProps {
  trades: Trade[];
  stats: TradeStats | null;
  onInsertTrade: (tradeId: string) => void;
  onInsertScreenshot: (imageId: string) => void;
  onInsertStats: (text: string) => void;
  onPreviewImage: (image: TradeImage) => void;
}

export default function MaterialDrawer({
  trades,
  stats,
  onInsertTrade,
  onInsertScreenshot,
  onInsertStats,
  onPreviewImage,
}: MaterialDrawerProps) {
  const { t } = useTranslation();
  const { displayMoney, formatMoney } = useJournalSettings();

  const images = trades.flatMap((trade) =>
    (trade.images ?? []).map((image) => ({ trade, image })),
  );

  return (
    <aside className="hidden w-[250px] shrink-0 flex-col gap-4 rounded-xl border border-border bg-card/40 p-3 shadow-sm lg:flex">
      <div className="text-ui font-medium text-foreground">{t("dailyReview.material.title")}</div>
      <Section title={t("dailyReview.material.trades")} empty={trades.length === 0}>
        {trades.map((trade) => (
          <div
            key={trade.id}
            className="flex items-center justify-between gap-2 rounded-md border border-border bg-[var(--chip-bg)] px-2 py-1"
          >
            <div className="min-w-0">
              <div className="truncate text-ui">{trade.symbol}</div>
              <div className="text-caption text-muted-foreground">
                {t(trade.direction === "long" ? "journal.long" : "journal.short")}
              </div>
            </div>
            <span
              className={cn(
                "text-ui font-semibold",
                trade.pnl != null && trade.pnl < 0
                  ? "text-destructive"
                  : "text-[var(--success)]",
              )}
            >
              {displayMoney(trade.pnl, { signed: true })}
            </span>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onInsertTrade(trade.id)}
              aria-label={t("dailyReview.material.insert")}
            >
              <Plus />
            </Button>
          </div>
        ))}
      </Section>

      <Section title={t("dailyReview.material.screenshots")} empty={images.length === 0}>
        <div className="grid grid-cols-2 gap-2">
          {images.map(({ trade, image }) => (
            <div
              key={image.id}
              className="overflow-hidden rounded-md border border-border bg-muted/30"
            >
              <button
                type="button"
                className="block w-full"
                onClick={() => onPreviewImage(image)}
              >
                <img
                  src={authedAssetUrl(image.url)}
                  alt={image.original_name || trade.symbol}
                  className="aspect-video w-full object-cover"
                />
              </button>
              <div className="flex items-center justify-between px-1 py-0.5">
                <span className="truncate text-caption text-muted-foreground">
                  {trade.symbol}
                </span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => onInsertScreenshot(image.id)}
                  aria-label={t("dailyReview.material.insert")}
                >
                  <Plus />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title={t("dailyReview.material.stats")} empty={!stats}>
        {stats && (
          <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-[var(--chip-bg)] p-2">
            <div className="text-caption text-muted-foreground">
              {t("dailyReview.material.statsLine", {
                trades: stats.total_trades,
                pnl: formatMoney(stats.total_pnl, { signed: true }),
                winRate: ((stats.win_rate ?? 0) * 100).toFixed(0),
              })}
            </div>
            <Button
              variant="ghost"
              size="icon-xs"
              style={dailyReviewControlStyle}
              onClick={() =>
                onInsertStats(
                  t("dailyReview.material.statsLine", {
                    trades: stats.total_trades,
                    pnl: formatMoney(stats.total_pnl, { signed: true }),
                    winRate: ((stats.win_rate ?? 0) * 100).toFixed(0),
                  }),
                )
              }
              aria-label={t("dailyReview.material.insert")}
            >
              <Plus />
            </Button>
          </div>
        )}
      </Section>
    </aside>
  );
}

function Section({
  title,
  empty,
  children,
}: {
  title: string;
  empty: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <div className="text-caption uppercase tracking-wide text-muted-foreground">{title}</div>
      {empty ? (
        <div className="text-caption text-muted-foreground">—</div>
      ) : (
        <div className="flex flex-col gap-2">{children}</div>
      )}
    </section>
  );
}
