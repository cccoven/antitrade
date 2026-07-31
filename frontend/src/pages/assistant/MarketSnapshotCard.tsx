import ReactECharts from "echarts-for-react";
import { CircleAlert, Clock3, Database } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { MarketSnapshotArtifactData } from "@/api/client";

function formatNumber(value: number | null | undefined, locale: string, digits = 4): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: digits,
  }).format(value);
}

function formatAsOf(value: string | null | undefined, locale: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function MarketSnapshotCard({ data }: { data: MarketSnapshotArtifactData }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage || i18n.language;

  if (data.error) {
    return (
      <Card className="mb-3 gap-0 rounded-lg border-destructive/30 bg-destructive/5 py-0 shadow-none">
        <CardContent className="flex items-start gap-2 px-3 py-3 text-caption text-muted-foreground">
          <CircleAlert className="mt-0.5 size-[var(--icon-sm)] shrink-0 text-destructive" />
          <div>
            <div className="font-medium text-foreground">{t("assistant.market.unavailable")}</div>
            <div className="mt-0.5">{t(`assistant.market.error.${data.error}`, { defaultValue: data.error })}</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const candles = [...(data.recent_candles ?? [])]
    .reverse()
    .filter((candle) => (
      candle.open != null && candle.high != null && candle.low != null && candle.close != null
    ));
  const quote = data.quote ?? {};
  const technicals = data.technicals ?? {};
  const percentChange = quote.percent_change;
  const positive = percentChange != null && percentChange >= 0;
  const chartOption = {
    animation: false,
    grid: { left: 2, right: 2, top: 5, bottom: 2 },
    xAxis: {
      type: "category",
      data: candles.map((candle) => candle.datetime ?? ""),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    yAxis: {
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    tooltip: { show: false },
    series: [{
      type: "candlestick",
      data: candles.map((candle) => [candle.open, candle.close, candle.low, candle.high]),
      itemStyle: {
        color: "var(--success)",
        color0: "var(--danger)",
        borderColor: "var(--success)",
        borderColor0: "var(--danger)",
      },
    }],
  };
  const metrics = [
    ["SMA20", technicals.sma20],
    ["SMA50", technicals.sma50],
    ["RSI14", technicals.rsi14],
    ["ATR14", technicals.atr14],
    [t("assistant.market.high20"), technicals.high20],
    [t("assistant.market.low20"), technicals.low20],
  ];

  return (
    <Card className="mb-3 gap-0 overflow-hidden rounded-lg bg-[var(--panel-card-bg)] py-0 shadow-none">
      <CardHeader className="flex flex-row items-start justify-between gap-3 border-b border-border px-3 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-subheading font-semibold">{data.symbol || "—"}</span>
            {data.asset_class ? <Badge variant="outline" className="text-micro">{data.asset_class}</Badge> : null}
            {data.interval ? <Badge variant="secondary" className="text-micro">{data.interval}</Badge> : null}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-micro text-muted-foreground">
            <span className="flex items-center gap-1"><Database className="size-[var(--icon-xs)]" />{data.provider || "—"}</span>
            <span className="flex items-center gap-1"><Clock3 className="size-[var(--icon-xs)]" />{formatAsOf(data.as_of, locale)}</span>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-heading font-semibold tabular-nums">{formatNumber(quote.price, locale, 6)}</div>
          <div className={cn(
            "mt-0.5 text-caption font-medium tabular-nums",
            percentChange == null ? "text-muted-foreground" : positive ? "text-[var(--success)]" : "text-[var(--danger)]",
          )}>
            {percentChange == null ? "—" : `${positive ? "+" : ""}${formatNumber(percentChange, locale, 2)}%`}
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-3 py-3">
        {candles.length > 1 ? (
          <ReactECharts option={chartOption} style={{ height: 128 }} opts={{ renderer: "svg" }} />
        ) : (
          <div className="flex h-20 items-center justify-center text-caption text-muted-foreground">
            {t("assistant.market.noCandles")}
          </div>
        )}
        <div className="mt-2 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
          {metrics.map(([label, value]) => (
            <div key={String(label)} className="rounded-md bg-muted/35 px-2 py-1.5">
              <div className="text-micro text-muted-foreground">{label}</div>
              <div className="mt-0.5 text-caption font-medium tabular-nums">{formatNumber(value as number | null | undefined, locale, 4)}</div>
            </div>
          ))}
        </div>
        {data.warnings?.length ? (
          <div className="mt-2 flex items-start gap-1.5 text-micro text-muted-foreground">
            <CircleAlert className="mt-0.5 size-[var(--icon-xs)] shrink-0" />
            <span>{data.warnings.map((warning) => t(`assistant.market.warning.${warning}`, { defaultValue: warning })).join(" · ")}</span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
