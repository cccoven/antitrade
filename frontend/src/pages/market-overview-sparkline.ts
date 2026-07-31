import type { MarketOverviewQuote } from "@/api/client";

const MARKET_SPARKLINE_STORAGE_KEY = "antitrade.marketOverviewSparklines";
export const MARKET_SPARKLINE_POINT_LIMIT = 32;

export interface MarketSparklinePoint {
  time: string;
  price: number;
}

export type MarketSparklineHistory = Record<string, MarketSparklinePoint[]>;

export function appendMarketSparklineQuotes(
  current: MarketSparklineHistory,
  quotes: MarketOverviewQuote[],
): MarketSparklineHistory {
  const next = { ...current };

  for (const quote of quotes) {
    if (
      quote.price == null
      || !Number.isFinite(quote.price)
      || !quote.as_of
      || Number.isNaN(Date.parse(quote.as_of))
    ) {
      continue;
    }

    const samples = [
      ...(quote.sparkline ?? []),
      { time: quote.as_of, price: quote.price },
    ].filter(
      (point) =>
        Number.isFinite(point.price)
        && !Number.isNaN(Date.parse(point.time)),
    );
    const pointsByTime = new Map(
      (next[quote.symbol] ?? []).map((point) => [point.time, point]),
    );
    for (const point of samples) pointsByTime.set(point.time, point);
    const points = Array.from(pointsByTime.values());
    points.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
    next[quote.symbol] = points.slice(-MARKET_SPARKLINE_POINT_LIMIT);
  }

  return next;
}

export function readMarketSparklineHistory(): MarketSparklineHistory {
  if (typeof window === "undefined" || !window.localStorage) return {};
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem(MARKET_SPARKLINE_STORAGE_KEY) ?? "{}",
    ) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};

    return Object.fromEntries(
      Object.entries(parsed).flatMap(([symbol, value]) => {
        if (!Array.isArray(value)) return [];
        const points = value.filter(
          (point): point is MarketSparklinePoint =>
            !!point
            && typeof point === "object"
            && typeof point.time === "string"
            && !Number.isNaN(Date.parse(point.time))
            && typeof point.price === "number"
            && Number.isFinite(point.price),
        );
        return [[symbol, points.slice(-MARKET_SPARKLINE_POINT_LIMIT)]];
      }),
    );
  } catch {
    return {};
  }
}

export function writeMarketSparklineHistory(value: MarketSparklineHistory) {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(MARKET_SPARKLINE_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // The chart can keep working in memory when storage is unavailable.
  }
}
