import test from "node:test";
import assert from "node:assert/strict";

import { getCalendarDayToneClass } from "../src/components/ui/calendar-day-tone.ts";

test("outside non-selected days use a dimmed tone", () => {
  assert.equal(
    getCalendarDayToneClass({
      outside: true,
      selected: false,
      range_start: false,
      range_end: false,
      range_middle: false,
    }),
    "text-muted-foreground/60"
  );
});

test("selected days keep selected styling priority", () => {
  assert.equal(
    getCalendarDayToneClass({
      outside: true,
      selected: true,
      range_start: false,
      range_end: false,
      range_middle: false,
    }),
    undefined
  );
});
