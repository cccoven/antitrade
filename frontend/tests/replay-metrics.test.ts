import assert from "node:assert/strict";
import test from "node:test";

import { calculateReplayExcursion } from "../src/pages/replay-metrics.ts";

test("long MAE stays at zero when price never moves below entry", () => {
  const result = calculateReplayExcursion({
    bars: [
      { high: 28_154.25, low: 28_057.75 },
      { high: 28_180, low: 28_070 },
    ],
    openIndex: 0,
    heldEndIndex: 0,
    openPrice: 27_940,
    direction: "long",
  });

  assert.deepEqual(result, {
    mfe: 214.25,
    mae: 0,
  });
});

test("short MFE and MAE use signed trade-direction excursion", () => {
  const result = calculateReplayExcursion({
    bars: [{ high: 105, low: 92 }],
    openIndex: 0,
    heldEndIndex: 0,
    openPrice: 100,
    direction: "short",
  });

  assert.deepEqual(result, {
    mfe: 8,
    mae: -5,
  });
});

test("bars before the entry index do not affect excursion", () => {
  const result = calculateReplayExcursion({
    bars: [
      { high: 999, low: 1 },
      { high: 104, low: 98 },
    ],
    openIndex: 1,
    heldEndIndex: 1,
    openPrice: 100,
    direction: "long",
  });

  assert.deepEqual(result, {
    mfe: 4,
    mae: -2,
  });
});
