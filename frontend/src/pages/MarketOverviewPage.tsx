import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Activity, ArrowDownRight, ArrowUpRight, Clock3, Newspaper, RefreshCw, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  animatedLineTabClassName,
  Tabs,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ControlStrip from "@/components/ControlStrip";
import BriefingCard from "@/components/radar/BriefingCard";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/i18n-context";
import {
  fetchLatestBriefing,
  fetchDailyMarketBriefing,
  fetchMarketOverview,
  type DailyMarketBriefing,
  type FeedBriefing,
  type MarketOverview,
  type MarketOverviewMacro,
  type MarketOverviewQuote,
} from "@/api/client";
import { marketOverviewControlSizes } from "./market-overview-ui-config";
import {
  appendMarketSparklineQuotes,
  readMarketSparklineHistory,
  writeMarketSparklineHistory,
  type MarketSparklineHistory,
} from "./market-overview-sparkline";

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value == null) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

type OverviewGroup = "all" | "indices" | "rates" | "energy" | "metals" | "forex" | "crypto";
type PriceMove = "up" | "down";

const OVERVIEW_GROUPS: OverviewGroup[] = ["all", "indices", "rates", "energy", "metals", "forex", "crypto"];
const EMPTY_QUOTE_DEFINITIONS = [
  ["NQ", "Nasdaq Futures", "indices", "USD"],
  ["ES", "S&P Futures", "indices", "USD"],
  ["SPY", "S&P 500", "indices", "USD"],
  ["QQQ", "Nasdaq 100", "indices", "USD"],
  ["IWM", "Russell 2000", "indices", "USD"],
  ["DIA", "Dow Jones", "indices", "USD"],
  ["TLT", "US 20Y Treasury", "rates", "USD"],
  ["HYG", "High Yield Bonds", "rates", "USD"],
  ["USO", "WTI Oil ETF", "energy", "USD"],
  ["GLD", "Gold ETF", "metals", "USD"],
  ["SLV", "Silver ETF", "metals", "USD"],
  ["GC", "Gold Futures", "metals", "USD"],
  ["XAU/USD", "Gold Spot", "metals", "USD"],
  ["EUR/USD", "EUR/USD", "forex", "USD"],
  ["GBP/USD", "GBP/USD", "forex", "USD"],
  ["USD/JPY", "USD/JPY", "forex", "JPY"],
  ["AUD/USD", "AUD/USD", "forex", "USD"],
  ["BTC/USD", "Bitcoin", "crypto", "USD"],
  ["ETH/USD", "Ethereum", "crypto", "USD"],
  ["SOL/USD", "Solana", "crypto", "USD"],
] as const;
const DEFAULT_GROUPS = Object.fromEntries(
  EMPTY_QUOTE_DEFINITIONS.map(([symbol, , group]) => [symbol, group]),
) as Record<string, Exclude<OverviewGroup, "all">>;
const EMPTY_QUOTES: MarketOverviewQuote[] = EMPTY_QUOTE_DEFINITIONS.map(
  ([symbol, label, group, currency]) => ({
    symbol,
    label,
    group,
    price: null,
    change: null,
    percent_change: null,
    currency,
    exchange: null,
    as_of: null,
  }),
);

function quoteGroup(item: MarketOverviewQuote) {
  return item.group ?? DEFAULT_GROUPS[item.symbol] ?? "indices";
}

function marketTone(change: number | null | undefined) {
  if (change == null || change === 0) return "text-[var(--market-flat)]";
  return change > 0 ? "text-[var(--market-up)]" : "text-[var(--market-down)]";
}

function stateTone(value: string | null) {
  if (value == null) return "text-[var(--market-flat)]";
  if (["risk_on", "up", "stronger"].includes(value)) return "text-[var(--market-up)]";
  return "text-[var(--market-down)]";
}

function WorkspacePanel({
  title,
  meta,
  children,
  className,
}: {
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("overflow-hidden rounded-[var(--radius-data-panel)] border border-[var(--data-grid-line)] bg-[var(--data-panel-bg)]", className)}>
      <header className="flex min-h-9 items-center justify-between gap-3 border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] px-3">
        <h2 className="text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">{title}</h2>
        {meta ? <div className="text-micro text-muted-foreground">{meta}</div> : null}
      </header>
      {children}
    </section>
  );
}

function MarketContextBar({
  items,
  provider,
  loading,
  available,
}: {
  items: MarketOverviewQuote[];
  provider?: string;
  loading: boolean;
  available: boolean;
}) {
  const { t } = useTranslation();
  const status = loading
    ? t("marketOverview.feed.loading")
    : available
      ? t("marketOverview.feed.live")
      : t("marketOverview.feed.unavailable");

  return (
    <div className="sticky top-[var(--page-topbar-height)] z-[11] flex min-h-10 border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)]">
      <div className="market-ticker-viewport min-w-0 flex-1">
        <div className="market-ticker-track flex w-max">
          {([false, true] as const).map((duplicate) => (
            <div
              key={duplicate ? "duplicate" : "primary"}
              className="flex shrink-0"
              aria-hidden={duplicate || undefined}
            >
              {items.map((item) => (
                <div key={item.symbol} className="flex h-10 min-w-max flex-none items-center justify-center gap-3 whitespace-nowrap border-r border-[var(--data-grid-line)] px-3">
                  <span className="market-data-value text-micro font-semibold text-foreground">{item.symbol}</span>
                  <span className="market-data-value text-caption text-foreground">{formatNumber(item.price, 4)}</span>
                  <span className={cn("market-data-value text-micro", marketTone(item.percent_change))}>
                    {item.percent_change == null ? "—" : `${item.percent_change >= 0 ? "+" : ""}${item.percent_change.toFixed(2)}%`}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="hidden shrink-0 items-center gap-2 px-3 text-micro text-muted-foreground lg:flex">
        <span className={cn("size-1.5 rounded-full", loading ? "animate-pulse bg-[var(--market-warning)]" : available ? "bg-[var(--market-up)]" : "bg-[var(--market-down)]")} />
        <span className="market-data-value">{provider?.replace(/_/g, " ").toUpperCase() ?? "DATA"}</span>
        <span>·</span>
        <span>{status}</span>
      </div>
    </div>
  );
}

function QuoteSparkline({
  values,
  positive,
}: {
  values: number[];
  positive: boolean;
}) {
  if (values.length === 0) {
    return <div className="h-8 border-b border-dashed border-border/60" />;
  }

  const width = 236;
  const height = 32;
  const chartValues = values.length === 1 ? [values[0], values[0]] : values;
  const minimum = Math.min(...chartValues);
  const maximum = Math.max(...chartValues);
  const span = maximum - minimum;
  const points = chartValues.map((value, index) => {
    const x = (index / (chartValues.length - 1)) * width;
    const y = span === 0
      ? height / 2
      : height - 3 - ((value - minimum) / span) * (height - 6);
    return [x, y] as const;
  });
  const linePoints = points.map(([x, y]) => `${x},${y}`).join(" ");
  const areaPoints = `0,${height} ${linePoints} ${width},${height}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      className={cn(
        "h-8 w-full",
        positive ? "text-[var(--market-up)]" : "text-[var(--market-down)]",
      )}
    >
      <polygon points={areaPoints} fill="currentColor" opacity="0.09" />
      <polyline
        points={linePoints}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function QuoteCard({
  item,
  priceMove,
  sparkline,
}: {
  item: MarketOverviewQuote;
  priceMove?: PriceMove;
  sparkline: number[];
}) {
  const change = item.percent_change;
  const positive = change != null && change >= 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  const sparklineValues = sparkline.length >= 2
    ? sparkline
    : [item.open, item.price].filter((value): value is number => value != null);
  return (
    <Card className="w-[260px] flex-none snap-start gap-0 overflow-hidden rounded-[var(--radius-data-panel)] border-[var(--data-grid-line)] bg-[var(--data-panel-bg)] py-0 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] px-3 py-2 pb-2!">
        <div className="min-w-0">
          <div className="truncate text-micro uppercase tracking-wide text-muted-foreground">{item.label}</div>
          <div className="market-data-value mt-1 text-caption font-semibold">{item.symbol}</div>
        </div>
        {change != null ? <Icon className={cn("size-[var(--icon-sm)]", marketTone(change))} /> : null}
      </CardHeader>
      <CardContent className="px-3 py-3">
        <div className="flex items-baseline justify-between gap-2">
          <span className={cn(
            "market-data-value text-heading font-semibold transition-colors duration-700",
            priceMove === "up" && "text-[var(--market-up)]",
            priceMove === "down" && "text-[var(--market-down)]",
          )}>{formatNumber(item.price, 4)}</span>
          <span className={cn("market-data-value text-caption", marketTone(change))}>
            {change == null ? "—" : `${positive ? "+" : ""}${change.toFixed(2)}%`}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between gap-2 text-micro text-muted-foreground">
          <span className="market-data-value">{item.change == null ? "—" : `${item.change >= 0 ? "+" : ""}${formatNumber(item.change, 4)}`}</span>
          <span>{[item.exchange, item.currency].filter(Boolean).join(" · ") || "—"}</span>
        </div>
        <div className="mt-2 flex justify-between text-micro text-muted-foreground">
          <span>L {formatNumber(item.low, 4)}</span>
          <span>H {formatNumber(item.high, 4)}</span>
        </div>
        <div className="mt-1">
          <QuoteSparkline values={sparklineValues} positive={positive} />
        </div>
      </CardContent>
    </Card>
  );
}

function MacroCard({ item }: { item: MarketOverviewMacro }) {
  const latest = item.latest?.value;
  const previous = item.previous?.value;
  const delta = latest != null && previous != null ? latest - previous : null;
  const positive = delta != null && delta >= 0;
  return (
    <Card className="gap-0 rounded-none border-0 border-b border-[var(--data-grid-line)] bg-transparent py-0 shadow-none last:border-b-0">
      <CardContent className="flex min-h-14 items-center justify-between gap-3 px-3 py-2">
        <div>
          <div className="text-caption font-medium text-foreground">{item.label}</div>
          <div className="mt-1 text-micro text-muted-foreground">{item.latest?.date ?? item.error ?? "—"}</div>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <span className="market-data-value text-ui font-semibold">{formatNumber(latest, 3)}</span>
          <span className={cn("market-data-value min-w-14 text-right text-caption", marketTone(delta))}>
            {delta == null ? "—" : `${positive ? "+" : ""}${delta.toFixed(2)}`}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function BriefingTag({ label, value }: { label: string; value: string }) {
  return <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/30 px-2 py-1 text-micro"><span className="text-muted-foreground">{label}</span><span className="text-foreground">{value}</span></span>;
}

function DailyBriefingCard({ briefing, loading, failed }: { briefing: DailyMarketBriefing | null; loading: boolean; failed: boolean }) {
  const { t } = useTranslation();
  if (!briefing) {
    return (
      <Card className="rounded-[10px] bg-[var(--panel-card-bg)] py-4">
        <CardContent className="text-ui text-muted-foreground">
          {loading ? t("marketOverview.brief.loading") : failed ? t("marketOverview.error.briefing_unavailable") : t("marketOverview.brief.empty")}
        </CardContent>
      </Card>
    );
  }

  const generatedAt = new Date(briefing.generated_at);
  const directionClass = {
    supportive: "bg-[var(--market-up)]",
    restrictive: "bg-[var(--market-down)]",
    mixed: "bg-[var(--market-warning)]",
  } as const;
  const scenarios = ["bullish", "bearish", "no_trade"] as const;

  return (
    <Card className="gap-3 rounded-[10px] border-primary/20 bg-[var(--panel-card-bg)] py-4">
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 px-4">
        <div className="flex min-w-0 items-start gap-2">
          <Sparkles className="mt-0.5 size-[var(--icon-sm)] shrink-0 text-primary" />
          <div>
            <CardTitle>{t("marketOverview.brief.title")}</CardTitle>
            <div className="mt-1 text-micro text-muted-foreground">{t("marketOverview.brief.updated", { time: generatedAt.toLocaleTimeString() })}</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <BriefingTag label={t("marketOverview.brief.bias")} value={t(`marketOverview.brief.value.${briefing.regime.bias}`)} />
          <BriefingTag label={t("marketOverview.brief.volatility")} value={t(`marketOverview.brief.value.${briefing.regime.volatility}`)} />
          <BriefingTag label={t("marketOverview.brief.risk")} value={t(`marketOverview.brief.value.${briefing.regime.risk}`)} />
          <BriefingTag label={t("marketOverview.brief.confidence")} value={t(`marketOverview.brief.value.${briefing.regime.confidence}`)} />
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 px-4">
        <p className="text-ui leading-relaxed text-foreground">{briefing.summary}</p>

        <div className="grid gap-3 lg:grid-cols-3">
          <div className="rounded-md border border-border bg-muted/20 p-3">
            <div className="mb-2 text-caption font-semibold text-muted-foreground">{t("marketOverview.brief.drivers")}</div>
            <div className="space-y-2">
              {briefing.drivers.length ? briefing.drivers.map((item, index) => (
                <div key={`${item.label}-${index}`} className="flex items-start gap-2 text-caption">
                  <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", directionClass[item.direction])} />
                  <div><span className="font-medium text-foreground">{item.label}</span><span className="ml-1 text-muted-foreground">{item.detail}</span></div>
                </div>
              )) : <div className="text-caption text-muted-foreground">{t("marketOverview.brief.noDrivers")}</div>}
            </div>
          </div>

          <div className="rounded-md border border-border bg-muted/20 p-3">
            <div className="mb-2 text-caption font-semibold text-muted-foreground">{t("marketOverview.brief.catalysts")}</div>
            <div className="space-y-2">
              {briefing.catalysts.length ? briefing.catalysts.slice(0, 3).map((item, index) => (
                <a key={`${item.date}-${index}`} className="flex items-start justify-between gap-2 text-caption hover:text-primary" href={item.source_url ?? undefined} target={item.source_url ? "_blank" : undefined} rel={item.source_url ? "noreferrer" : undefined}>
                  <span className="min-w-0 truncate"><span className="mr-1 text-muted-foreground">{new Date(item.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>{item.title}</span>
                  <span className={cn("shrink-0 rounded-full px-1.5 py-0.5 text-micro", item.impact === "high" ? "bg-red-500/10 text-[var(--market-down)]" : "bg-amber-500/10 text-[var(--market-warning)]")}>{t(`marketOverview.calendarImpact.${item.impact}`)}</span>
                </a>
              )) : <div className="text-caption text-muted-foreground">{t("marketOverview.brief.noEvents")}</div>}
            </div>
          </div>

          <div className="rounded-md border border-border bg-muted/20 p-3">
            <div className="mb-2 flex items-center gap-1.5 text-caption font-semibold text-muted-foreground"><Newspaper className="size-[var(--icon-xs)]" />{t("marketOverview.brief.news")}</div>
            <div className="space-y-2">
              {briefing.news.length ? briefing.news.slice(0, 3).map((item, index) => (
                <a key={`${item.url}-${index}`} className="block text-caption hover:text-primary" href={item.url} target="_blank" rel="noreferrer"><span className="line-clamp-1">{item.title}</span><span className="text-micro text-muted-foreground">{item.source}</span></a>
              )) : <div className="text-caption text-muted-foreground">{t("marketOverview.brief.noNews")}</div>}
            </div>
          </div>
        </div>

        <div>
          <div className="mb-2 text-caption font-semibold text-muted-foreground">{t("marketOverview.brief.playbook")}</div>
          <div className="grid gap-2 md:grid-cols-3">
            {scenarios.map((scenario) => <div key={scenario} className="rounded-md border border-border bg-muted/20 px-3 py-2"><div className="text-caption font-medium text-foreground">{t(`marketOverview.brief.scenario.${scenario}`)}</div><div className="mt-1 text-caption leading-relaxed text-muted-foreground">{briefing.playbook[scenario]}</div></div>)}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border/50 pt-2 text-micro text-muted-foreground">
          <span>{t("marketOverview.brief.sources")}</span>
          {briefing.sources.map((source) => source.url ? <a key={`${source.kind}-${source.name}`} className="hover:text-foreground" href={source.url} target="_blank" rel="noreferrer">{source.name}</a> : <span key={`${source.kind}-${source.name}`}>{source.name}</span>)}
          <span>·</span><span>{briefing.model === "rule" ? t("marketOverview.brief.ruleModel") : t("marketOverview.brief.aiModel")}</span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function MarketOverviewPage() {
  const { t } = useTranslation();
  const { resolvedLanguage } = useI18n();
  const navigate = useNavigate();
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [briefing, setBriefing] = useState<FeedBriefing | null>(null);
  const [dailyBriefing, setDailyBriefing] = useState<DailyMarketBriefing | null>(null);
  const [dailyBriefingFailed, setDailyBriefingFailed] = useState(false);
  const [marketLoading, setMarketLoading] = useState(false);
  const [dailyBriefingLoading, setDailyBriefingLoading] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [activeGroup, setActiveGroup] = useState<OverviewGroup>("all");
  const [priceMoves, setPriceMoves] = useState<Record<string, PriceMove>>({});
  const [sparklineHistory, setSparklineHistory] = useState<MarketSparklineHistory>(
    readMarketSparklineHistory,
  );
  const quoteStripRef = useRef<HTMLDivElement>(null);
  const previousPrices = useRef<Record<string, number>>({});
  const priceMoveTimer = useRef<number | null>(null);
  const briefingRequestId = useRef(0);

  const applyOverview = useCallback((value: MarketOverview) => {
    const moves: Record<string, PriceMove> = {};
    const nextPrices: Record<string, number> = {};
    value.quotes.items.forEach((item) => {
      if (item.price == null) return;
      nextPrices[item.symbol] = item.price;
      const previous = previousPrices.current[item.symbol];
      if (previous != null && previous !== item.price) {
        moves[item.symbol] = item.price > previous ? "up" : "down";
      }
    });
    previousPrices.current = nextPrices;
    setSparklineHistory((current) => {
      const nextHistory = appendMarketSparklineQuotes(current, value.quotes.items);
      writeMarketSparklineHistory(nextHistory);
      return nextHistory;
    });
    setOverview(value);
    setUpdatedAt(new Date(value.cache?.fetched_at ?? Date.now()));
    if (Object.keys(moves).length) {
      setPriceMoves(moves);
      if (priceMoveTimer.current != null) window.clearTimeout(priceMoveTimer.current);
      priceMoveTimer.current = window.setTimeout(() => setPriceMoves({}), 900);
    }
  }, []);

  const loadMarket = useCallback(async (forceRefresh = false, silent = false) => {
    if (!silent) setMarketLoading(true);
    try {
      applyOverview(await fetchMarketOverview(forceRefresh, silent));
    } catch {
      // Background refreshes stay quiet; interactive errors use the shared toast.
    } finally {
      if (!silent) setMarketLoading(false);
    }
  }, [applyOverview]);

  const loadBriefings = useCallback(async (forceRefresh = false) => {
    const requestId = ++briefingRequestId.current;
    setDailyBriefingFailed(false);
    setBriefing(null);
    void fetchLatestBriefing(resolvedLanguage).then(
      (value) => {
        if (briefingRequestId.current === requestId) setBriefing(value);
      },
      () => {
        if (briefingRequestId.current === requestId) setBriefing(null);
      },
    );
    setDailyBriefingLoading(true);
    try {
      const value = await fetchDailyMarketBriefing(resolvedLanguage, forceRefresh);
      if (briefingRequestId.current === requestId) setDailyBriefing(value);
    } catch {
      if (briefingRequestId.current === requestId) setDailyBriefingFailed(true);
    } finally {
      if (briefingRequestId.current === requestId) setDailyBriefingLoading(false);
    }
  }, [resolvedLanguage]);

  const load = useCallback((forceRefresh = false) => {
    void loadMarket(forceRefresh);
    void loadBriefings(forceRefresh);
  }, [loadBriefings, loadMarket]);

  useEffect(() => { void load(false); }, [load]);
  useEffect(() => {
    const refreshVisibleMarket = () => {
      if (document.visibilityState === "visible") void loadMarket(false, true);
    };
    const timer = window.setInterval(refreshVisibleMarket, 30_000);
    document.addEventListener("visibilitychange", refreshVisibleMarket);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshVisibleMarket);
      if (priceMoveTimer.current != null) window.clearTimeout(priceMoveTimer.current);
    };
  }, [loadMarket]);

  const states = useMemo(() => {
    if (!overview) return [];
    return [
      ["risk", overview.states.risk], ["equities", overview.states.equities],
      ["crypto", overview.states.crypto], ["dollar", overview.states.dollar],
      ["gold", overview.states.gold],
    ] as const;
  }, [overview]);
  const quoteItems = overview?.quotes.items.length ? overview.quotes.items : EMPTY_QUOTES;
  const visibleQuoteItems = activeGroup === "all"
    ? quoteItems
    : quoteItems.filter((item) => quoteGroup(item) === activeGroup);

  useEffect(() => {
    if (quoteStripRef.current) quoteStripRef.current.scrollLeft = 0;
  }, [activeGroup]);
  const quotesAvailable = Boolean(overview?.quotes.items.length);
  const quoteAsOf = overview?.quotes.items.reduce<string | undefined>((latest, item) => {
    if (!item.as_of) return latest;
    return !latest || Date.parse(item.as_of) > Date.parse(latest) ? item.as_of : latest;
  }, undefined);

  return (
    <div className="page-stack page-stack-journal market-overview-page min-h-full bg-background">
      <ControlStrip
        className="control-strip-flush"
        aside={
          <TooltipIconButton
            label={t("marketOverview.refresh")}
            variant="outline"
            size={marketOverviewControlSizes.refreshAction}
            style={marketOverviewControlSizes.buttonStyle}
            onClick={() => void load(true)}
            disabled={marketLoading || dailyBriefingLoading}
          >
            <RefreshCw className={cn(marketLoading && "animate-spin")} />
          </TooltipIconButton>
        }
      >
        <div className="flex min-w-0 items-center gap-3">
          <Activity className="size-[var(--icon-md)] text-primary" />
          <div className="title-description-stack">
            <div className="text-subheading font-semibold">{t("marketOverview.title")}</div>
            <div className="text-caption text-muted-foreground">
              {updatedAt
                ? `${t("marketOverview.updated", { time: updatedAt.toLocaleTimeString() })} · ${t("marketOverview.autoRefresh")}`
                : t("marketOverview.loading")}
            </div>
          </div>
        </div>
      </ControlStrip>

      <MarketContextBar
        items={quoteItems}
        provider={overview?.quotes.provider}
        loading={marketLoading}
        available={quotesAvailable}
      />

      <main className="flex flex-col gap-3 p-3">
        <section>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-caption font-semibold uppercase tracking-wide text-muted-foreground">{t("marketOverview.crossAsset")}</div>
            <div className="market-data-value text-micro text-muted-foreground">
              {quotesAvailable
                ? quoteAsOf
                  ? new Date(quoteAsOf).toLocaleTimeString()
                  : overview?.quotes.provider.replace(/_/g, " ").toUpperCase()
                : t(`marketOverview.error.${overview?.quotes.error ?? "unavailable"}`)}
            </div>
          </div>
          <Tabs
            className="mb-2 gap-0"
            value={activeGroup}
            onValueChange={(value) => setActiveGroup(value as OverviewGroup)}
          >
            <div className="overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <TabsList variant="line" className="h-7 gap-4 p-0">
                {OVERVIEW_GROUPS.map((group) => (
                  <TabsTrigger
                    key={group}
                    value={group}
                    className={animatedLineTabClassName}
                    style={marketOverviewControlSizes.buttonStyle}
                  >
                    {t(`marketOverview.group.${group}`)}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>
          </Tabs>
          <div
            ref={quoteStripRef}
            className="flex snap-x snap-proximity gap-2 overflow-x-auto pb-2 [scrollbar-color:var(--border)_transparent] [scrollbar-width:thin]"
            data-testid="cross-asset-quote-strip"
          >
            {visibleQuoteItems.map((item) => (
              <QuoteCard
                key={item.symbol}
                item={item}
                priceMove={priceMoves[item.symbol]}
                sparkline={(sparklineHistory[item.symbol] ?? []).map((point) => point.price)}
              />
            ))}
          </div>
        </section>

        <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.38fr)]">
          <div className="flex flex-col gap-3">
            <WorkspacePanel
              title={t("marketOverview.stateTitle")}
              meta={updatedAt ? t("marketOverview.updated", { time: updatedAt.toLocaleTimeString() }) : null}
            >
              <div className="grid grid-cols-2 md:grid-cols-5">
                {(states.length ? states : [
                  ["risk", null], ["equities", null], ["crypto", null], ["dollar", null], ["gold", null],
                ] as const).map(([name, value]) => (
                  <div key={name} className="border-b border-r border-[var(--data-grid-line)] px-3 py-3 last:border-r-0 md:border-b-0">
                    <div className="text-micro uppercase tracking-wide text-muted-foreground">{t(`marketOverview.state.${name}`)}</div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className={cn("size-1.5 rounded-full bg-current", stateTone(value))} />
                      <span className={cn("market-data-value text-ui font-semibold", stateTone(value))}>
                        {value ? t(`marketOverview.value.${value}`) : "—"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </WorkspacePanel>

            <WorkspacePanel title={t("marketOverview.macro")} meta="FRED">
              {!overview?.macro.length || overview.macro.every((item) => item.error === "macro_data_not_configured") ? (
                <div className="px-3 py-4 text-ui text-muted-foreground">{t("marketOverview.error.macro_data_not_configured")}</div>
              ) : (
                <div className="grid md:grid-cols-2">
                  {(overview?.macro ?? []).map((item) => <MacroCard key={item.series_id} item={item} />)}
                </div>
              )}
            </WorkspacePanel>

            <DailyBriefingCard
              briefing={dailyBriefing}
              loading={dailyBriefingLoading}
              failed={dailyBriefingFailed}
            />
          </div>

          <div className="flex flex-col gap-3">
            <BriefingCard briefing={briefing} returnTo="/" />
            <WorkspacePanel title={t("marketOverview.workspaceTools")}>
              <div className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <Button size="sm" style={marketOverviewControlSizes.buttonStyle} onClick={() => navigate("/assistant")}>
                  <Sparkles />{t("marketOverview.openAssistant")}
                </Button>
                <Button variant="ghost" size="sm" style={marketOverviewControlSizes.buttonStyle} onClick={() => navigate("/tools/clock")}>
                  <Clock3 />{t("marketOverview.openMarketHours")}
                </Button>
              </div>
            </WorkspacePanel>
          </div>
        </section>
      </main>
    </div>
  );
}
