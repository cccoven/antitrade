import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { DailyReviewBundle } from "@/api/client";
import { dailyReviewControlStyle } from "@/pages/daily-review-ui-config";
import { useJournalSettings } from "@/journal/journal-settings-context";
import ReviewBody from "@/pages/daily-review/ReviewBody";
import type { ReviewBlock } from "@/pages/daily-review/parser";

type Mode = "long" | "cards";

export interface DailyReviewShareViewProps {
  date: string;
  title: string;
  blocks: ReviewBlock[];
  bundle: DailyReviewBundle | null;
}

export default function DailyReviewShareView({
  date,
  title,
  blocks,
  bundle,
}: DailyReviewShareViewProps) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<Mode>("long");
  const [showStats, setShowStats] = useState(true);
  const [showTrades, setShowTrades] = useState(true);

  const trades = bundle?.trades ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={mode}
          onValueChange={(v) => v && setMode(v as Mode)}
        >
          <ToggleGroupItem value="long" style={dailyReviewControlStyle}>
            {t("dailyReview.share.long")}
          </ToggleGroupItem>
          <ToggleGroupItem value="cards" style={dailyReviewControlStyle}>
            {t("dailyReview.share.cards")}
          </ToggleGroupItem>
        </ToggleGroup>
        <div className="flex flex-wrap gap-3 text-caption text-muted-foreground">
          <Toggle checked={showStats} onChange={setShowStats} label={t("dailyReview.share.stats")} />
          <Toggle checked={showTrades} onChange={setShowTrades} label={t("dailyReview.share.trades")} />
        </div>
      </div>

      {mode === "long" ? (
        <section className="mx-auto flex w-full max-w-[720px] flex-col gap-5 bg-background p-6 text-foreground">
          <ShareHeader date={date} title={title || t("dailyReview.titleNav")} />
          {showStats && <StatsBlock bundle={bundle} />}
          {showTrades && <TradesBlock bundle={bundle} />}
          <ReviewBody blocks={blocks} mode="share" trades={trades} />
        </section>
      ) : (
        <section className="grid gap-4 md:grid-cols-2">
          <CardFrame>
            <ShareHeader date={date} title={title || t("dailyReview.titleNav")} />
            {showStats && <StatsBlock bundle={bundle} />}
          </CardFrame>
          <CardFrame>
            <ReviewBody blocks={blocks} mode="share" trades={trades} />
          </CardFrame>
          {showTrades && (
            <CardFrame>
              <TradesBlock bundle={bundle} />
            </CardFrame>
          )}
        </section>
      )}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-1.5">
      <Checkbox checked={checked} onCheckedChange={(v) => onChange(Boolean(v))} />
      {label}
    </label>
  );
}

function ShareHeader({ date, title }: { date: string; title: string }) {
  return (
    <div className="title-description-stack border-b border-border pb-3">
      <h2 className="text-heading font-semibold text-foreground">{title}</h2>
      <div className="text-caption text-muted-foreground">{date}</div>
    </div>
  );
}

function StatsBlock({ bundle }: { bundle: DailyReviewBundle | null }) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();
  const stats = bundle?.stats;
  return (
    <div className="grid grid-cols-3 gap-2">
      <ShareMetric label={t("journal.tradeCount")} value={String(stats?.total_trades ?? 0)} />
      <ShareMetric label={t("journal.pnl")} value={displayMoney(stats?.total_pnl ?? 0, { signed: true })} />
      <ShareMetric label={t("journal.winRate")} value={`${((stats?.win_rate ?? 0) * 100).toFixed(1)}%`} />
    </div>
  );
}

function ShareMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-[var(--chip-bg)] p-3">
      <div className="text-caption text-muted-foreground">{label}</div>
      <div className="text-subheading text-foreground">{value}</div>
    </div>
  );
}

function TradesBlock({ bundle }: { bundle: DailyReviewBundle | null }) {
  const { displayMoney } = useJournalSettings();
  const trades = bundle?.trades ?? [];
  if (trades.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      {trades.slice(0, 8).map((trade) => (
        <div
          key={trade.id}
          className="flex justify-between gap-4 border-b border-border/60 py-1 text-ui"
        >
          <span>{trade.symbol}</span>
          <span>{displayMoney(trade.pnl, { signed: true })}</span>
        </div>
      ))}
    </div>
  );
}

function CardFrame({ children }: { children: ReactNode }) {
  return (
    <div className="aspect-[4/5] overflow-hidden rounded-md border border-border bg-background p-5 text-foreground">
      <div className="flex h-full flex-col gap-4">{children}</div>
    </div>
  );
}
