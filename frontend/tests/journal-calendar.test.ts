import test from "node:test";
import assert from "node:assert/strict";

import {
  buildJournalCalendarYearOptions,
  setJournalCalendarMonth,
  toJournalMonthKey,
} from "../src/pages/journal-calendar";

test("journal calendar month keys use compact year-month format", () => {
  assert.equal(toJournalMonthKey(new Date("2026-04-13T09:30:00")), "2026-04");
});

test("journal calendar year options span around the active month", () => {
  assert.deepEqual(
    buildJournalCalendarYearOptions(new Date("2026-04-13T09:30:00"), 2, 1),
    [2024, 2025, 2026, 2027]
  );
});

test("journal calendar month selection always snaps to month start", () => {
  const selected = setJournalCalendarMonth(
    new Date("2026-04-13T09:30:00"),
    2025,
    0
  );
  assert.equal(selected.toISOString(), new Date("2025-01-01T00:00:00").toISOString());
});
