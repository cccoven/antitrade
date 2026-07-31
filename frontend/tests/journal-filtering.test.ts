import test from "node:test";
import assert from "node:assert/strict";

import {
  applyJournalSymbolDraft,
  buildJournalDayRange,
  buildJournalTradeQueryParams,
  getSelectedJournalDay,
} from "../src/pages/journal-filtering";

test("journal symbol drafts are trimmed before they become applied filters", () => {
  assert.equal(applyJournalSymbolDraft("  XAUUSD  "), "XAUUSD");
  assert.equal(applyJournalSymbolDraft("   "), "");
  assert.equal(applyJournalSymbolDraft("BTCUSD"), "BTCUSD");
});

test("journal trade query params are built only from applied filters", () => {
  assert.deepEqual(buildJournalTradeQueryParams("", "all", "all"), {});
  assert.deepEqual(buildJournalTradeQueryParams("XAUUSD", "all", "all"), {
    symbol: "XAUUSD",
  });
  assert.deepEqual(buildJournalTradeQueryParams("XAUUSD", "long", "open"), {
    symbol: "XAUUSD",
    direction: "long",
    position_status: "open",
  });
  assert.deepEqual(buildJournalTradeQueryParams("", "short", "closed"), {
    direction: "short",
    position_status: "closed",
  });
  const dateFiltered = buildJournalTradeQueryParams(
    "XAUUSD",
    "long",
    "all",
    "2026-04-13T00:00",
    "2026-04-13T23:59",
  );
  assert.equal(dateFiltered.symbol, "XAUUSD");
  assert.equal(dateFiltered.direction, "long");
  // date_from/date_to are converted to UTC ISO so SQLite string compare against
  // Z-suffixed open_time values is sound. The exact value depends on the test
  // host timezone, but it must round-trip back to the same wall clock.
  assert.equal(
    new Date(dateFiltered.date_from as string).getTime(),
    new Date("2026-04-13T00:00").getTime(),
  );
  assert.equal(
    new Date(dateFiltered.date_to as string).getTime(),
    new Date("2026-04-13T23:59").getTime(),
  );
});

test("journal calendar day ranges expand to the full selected local day", () => {
  const range = buildJournalDayRange(new Date("2026-04-13T09:30:00"));
  assert.deepEqual(range, {
    dateFrom: "2026-04-13T00:00",
    dateTo: "2026-04-13T23:59",
  });
});

test("journal selected day detection only returns exact full-day filters", () => {
  const selected = getSelectedJournalDay("2026-04-13T00:00", "2026-04-13T23:59");
  assert.equal(selected?.toISOString(), new Date("2026-04-13T00:00:00").toISOString());

  assert.equal(getSelectedJournalDay("2026-04-13T01:00", "2026-04-13T23:59"), null);
  assert.equal(getSelectedJournalDay("2026-04-13T00:00", "2026-04-14T23:59"), null);
});
