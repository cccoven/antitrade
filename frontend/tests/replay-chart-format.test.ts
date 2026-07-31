import assert from "node:assert/strict";
import test from "node:test";

import {
  formatReplayChartTick,
  formatReplayChartTime,
} from "../src/components/replay-chart-format.ts";

const BAR_AT_1614_UTC = 1_785_168_840;

test("chart ticks use the same local timezone as the replay inspector", () => {
  const tick = formatReplayChartTick(
    BAR_AT_1614_UTC,
    3,
    "en-US",
    "Asia/Shanghai",
  );

  assert.equal(tick, "00:14");
});

test("chart crosshair time includes the localized calendar date", () => {
  const label = formatReplayChartTime(
    BAR_AT_1614_UTC,
    "en-US",
    "Asia/Shanghai",
  );

  assert.match(label, /Jul 28/);
  assert.match(label, /00:14/);
});
