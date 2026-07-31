import test from "node:test";
import assert from "node:assert/strict";

import type { MarketHoursItem } from "../src/api/client.ts";
import { marketStateAt } from "../src/pages/market-hours/market-hours-utils.ts";

const market = {
  sessions: [
    { kind: "main", start_at: "2026-07-15T09:30:00Z", end_at: "2026-07-15T11:30:00Z" },
    { kind: "main", start_at: "2026-07-15T13:00:00Z", end_at: "2026-07-15T15:00:00Z" },
  ],
} as MarketHoursItem;

test("market state closes exactly at the lunch-break boundary", () => {
  assert.equal(marketStateAt(market, new Date("2026-07-15T11:29:59Z")), "main");
  assert.equal(marketStateAt(market, new Date("2026-07-15T11:30:00Z")), "closed");
});

test("market state reopens for the afternoon session and closes at its end", () => {
  assert.equal(marketStateAt(market, new Date("2026-07-15T13:00:00Z")), "main");
  assert.equal(marketStateAt(market, new Date("2026-07-15T15:00:00Z")), "closed");
});
