import assert from "node:assert/strict";
import test from "node:test";
import {
  createReplayPlaybackState,
  replayPlaybackReducer,
} from "../src/pages/replay-machine.ts";

test("replay pauses immediately before the entry candle is revealed", () => {
  let state = createReplayPlaybackState({
    startCursor: 2,
    decisionCursor: 5,
    totalBars: 10,
    speed: 1,
  });
  state = replayPlaybackReducer(state, { type: "PLAY" });
  state = replayPlaybackReducer(state, { type: "TICK" });
  state = replayPlaybackReducer(state, { type: "TICK" });
  state = replayPlaybackReducer(state, { type: "TICK" });

  assert.equal(state.status, "paused");
  assert.equal(state.cursor, 5);
  assert.equal(state.pauseReason, "decision");
});

test("resuming after the decision pause reveals the entry candle", () => {
  let state = createReplayPlaybackState({
    startCursor: 5,
    decisionCursor: 5,
    totalBars: 10,
    speed: 1,
  });
  state = replayPlaybackReducer(state, { type: "PLAY" });
  state = replayPlaybackReducer(state, { type: "TICK" });

  assert.equal(state.status, "playing");
  assert.equal(state.cursor, 6);
});

test("seeking backward rearms the decision pause", () => {
  let state = createReplayPlaybackState({
    startCursor: 2,
    decisionCursor: 5,
    totalBars: 10,
    speed: 1,
  });
  state = replayPlaybackReducer(state, { type: "SEEK", cursor: 7 });
  state = replayPlaybackReducer(state, { type: "SEEK", cursor: 3 });

  assert.equal(state.decisionPaused, false);
});

test("timeline seeking clamps to the replay bounds and pauses playback", () => {
  let state = createReplayPlaybackState({
    startCursor: 2,
    decisionCursor: 5,
    totalBars: 10,
    speed: 1,
  });
  state = replayPlaybackReducer(state, { type: "PLAY" });
  state = replayPlaybackReducer(state, { type: "SEEK", cursor: 99 });

  assert.equal(state.status, "completed");
  assert.equal(state.cursor, 10);
  assert.equal(state.pauseReason, "end");

  state = replayPlaybackReducer(state, { type: "SEEK", cursor: -10 });
  assert.equal(state.status, "paused");
  assert.equal(state.cursor, 1);
  assert.equal(state.pauseReason, "manual");
});

test("completed replay restarts from the configured context cursor", () => {
  let state = createReplayPlaybackState({
    startCursor: 3,
    decisionCursor: 5,
    totalBars: 6,
    speed: 1,
  });
  state = replayPlaybackReducer(state, { type: "SEEK", cursor: 6 });
  state = replayPlaybackReducer(state, { type: "PLAY" });

  assert.equal(state.status, "playing");
  assert.equal(state.cursor, 3);
});
