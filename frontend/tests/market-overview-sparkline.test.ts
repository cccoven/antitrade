import test from "node:test";
import assert from "node:assert/strict";

import type { MarketOverviewQuote } from "../src/api/client.ts";
import {
  appendMarketSparklineQuotes,
  MARKET_SPARKLINE_POINT_LIMIT,
} from "../src/pages/market-overview-sparkline.ts";

function quote(price: number, asOf: string): MarketOverviewQuote {
  return {
    symbol: "NQ",
    label: "Nasdaq Futures",
    price,
    change: null,
    percent_change: null,
    currency: "USD",
    exchange: "CME",
    as_of: asOf,
  };
}

test("market sparkline samples stay chronological and replace duplicate timestamps", () => {
  let history = appendMarketSparklineQuotes({}, [
    quote(102, "2026-07-28T02:00:00Z"),
    quote(101, "2026-07-28T01:00:00Z"),
  ]);
  history = appendMarketSparklineQuotes(history, [
    quote(103, "2026-07-28T02:00:00Z"),
  ]);

  assert.deepEqual(history.NQ, [
    { time: "2026-07-28T01:00:00Z", price: 101 },
    { time: "2026-07-28T02:00:00Z", price: 103 },
  ]);
});

test("market sparkline starts with provider history instead of a two-point line", () => {
  const item = quote(103, "2026-07-28T02:00:00Z");
  item.sparkline = [
    { time: "2026-07-28T01:57:00Z", price: 101 },
    { time: "2026-07-28T01:58:00Z", price: 102.5 },
    { time: "2026-07-28T01:59:00Z", price: 101.75 },
  ];

  const history = appendMarketSparklineQuotes({}, [item]);

  assert.deepEqual(
    history.NQ.map((point) => point.price),
    [101, 102.5, 101.75, 103],
  );
});

test("market sparkline keeps only the latest samples", () => {
  const samples = Array.from(
    { length: MARKET_SPARKLINE_POINT_LIMIT + 3 },
    (_, index) => quote(100 + index, new Date(1_700_000_000_000 + index * 60_000).toISOString()),
  );

  const history = appendMarketSparklineQuotes({}, samples);

  assert.equal(history.NQ.length, MARKET_SPARKLINE_POINT_LIMIT);
  assert.equal(history.NQ.at(0)?.price, 103);
});
