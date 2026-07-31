import test from "node:test";
import assert from "node:assert/strict";

import { mergeCalendarClassNames } from "../src/components/ui/calendar-classnames.ts";

test("calendar class overrides preserve weekday layout classes", () => {
  const merged = mergeCalendarClassNames({
    weekday: "text-[length:var(--font-caption)] font-normal text-muted-foreground",
    caption_label: "text-[length:var(--font-ui)] font-normal",
  });

  assert.match(merged.weekday ?? "", /flex-1/);
  assert.match(merged.weekday ?? "", /select-none/);
  assert.match(merged.weekday ?? "", /text-\[length:var\(--font-caption\)\]/);
  assert.match(merged.caption_label ?? "", /font-normal/);
});
