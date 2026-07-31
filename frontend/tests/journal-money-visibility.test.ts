import test from "node:test";
import assert from "node:assert/strict";

import {
  JOURNAL_AMOUNT_MASK,
  formatJournalMoney,
  maskJournalMoney,
} from "../src/journal/journal-currency.ts";

test("journal amounts are masked without changing missing values", () => {
  const formatted = formatJournalMoney(1234.5, "USD", "en", { signed: true });

  assert.equal(maskJournalMoney(1234.5, formatted, false), JOURNAL_AMOUNT_MASK);
  assert.equal(maskJournalMoney(1234.5, formatted, true), formatted);
  assert.equal(maskJournalMoney(null, "—", false), "—");
});
