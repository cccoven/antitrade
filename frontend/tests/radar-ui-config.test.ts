import test from "node:test";
import assert from "node:assert/strict";

import { radarControlSizes, RADAR_CATEGORIES } from "../src/pages/radar-ui-config.ts";

test("radar control sizes use ui font token", () => {
  assert.equal(radarControlSizes.fontSize, "var(--font-ui)");
  assert.equal(radarControlSizes.filter, "sm");
});

test("radar categories include all + core buckets", () => {
  assert.deepEqual(RADAR_CATEGORIES, ["all", "crypto", "forex", "macro", "general"]);
});
