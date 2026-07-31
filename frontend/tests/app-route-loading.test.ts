import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

test("home stays eager while non-home pages are route-split", () => {
  assert.match(
    source,
    /import MarketOverviewPage from ["']\.\/pages\/MarketOverviewPage["'];/,
  );
  assert.doesNotMatch(
    source,
    /import JournalPage from ["']\.\/pages\/JournalPage["'];/,
  );
  assert.match(
    source,
    /lazy\(\(\) => import\(["']\.\/pages\/JournalPage["']\)\)/,
  );
  assert.match(
    source,
    /lazy\(\(\) => import\(["']\.\/pages\/BacktestPage["']\)\)/,
  );
  assert.match(source, /<Suspense/);
});
