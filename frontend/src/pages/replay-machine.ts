export type ReplaySpeed = 0.5 | 1 | 2 | 4;

export interface ReplayPlaybackState {
  status: "paused" | "playing" | "completed";
  cursor: number;
  speed: ReplaySpeed;
  pauseReason: "decision" | "manual" | "end" | null;
  decisionPaused: boolean;
  startCursor: number;
  decisionCursor: number;
  totalBars: number;
}

export type ReplayPlaybackEvent =
  | {
      type: "RESET";
      startCursor: number;
      decisionCursor: number;
      totalBars: number;
      speed: number;
    }
  | { type: "PLAY" }
  | { type: "PAUSE" }
  | { type: "TICK" }
  | { type: "STEP"; delta: -1 | 1 }
  | { type: "SEEK"; cursor: number }
  | { type: "SET_SPEED"; speed: ReplaySpeed };

export function createReplayPlaybackState(config: {
  startCursor: number;
  decisionCursor: number;
  totalBars: number;
  speed: number;
}): ReplayPlaybackState {
  const speed = [0.5, 1, 2, 4].includes(config.speed)
    ? (config.speed as ReplaySpeed)
    : 1;
  const startCursor = clamp(config.startCursor, 1, config.totalBars);
  return {
    status: "paused",
    cursor: startCursor,
    speed,
    pauseReason: null,
    decisionPaused: startCursor >= config.decisionCursor,
    startCursor,
    decisionCursor: config.decisionCursor,
    totalBars: config.totalBars,
  };
}

export function replayPlaybackReducer(
  state: ReplayPlaybackState,
  event: ReplayPlaybackEvent,
): ReplayPlaybackState {
  switch (event.type) {
    case "RESET":
      return createReplayPlaybackState(event);
    case "PLAY":
      if (state.cursor >= state.totalBars) {
        return {
          ...state,
          status: "playing",
          cursor: state.startCursor,
          pauseReason: null,
          decisionPaused: state.startCursor >= state.decisionCursor,
        };
      }
      return { ...state, status: "playing", pauseReason: null };
    case "PAUSE":
      return { ...state, status: "paused", pauseReason: "manual" };
    case "SET_SPEED":
      return { ...state, speed: event.speed };
    case "STEP":
      return seek(state, state.cursor + event.delta);
    case "SEEK":
      return seek(state, event.cursor);
    case "TICK": {
      if (state.status !== "playing") return state;
      const next = Math.min(state.totalBars, state.cursor + 1);
      if (!state.decisionPaused && next >= state.decisionCursor) {
        return {
          ...state,
          status: "paused",
          cursor: state.decisionCursor,
          pauseReason: "decision",
          decisionPaused: true,
        };
      }
      if (next >= state.totalBars) {
        return {
          ...state,
          status: "completed",
          cursor: state.totalBars,
          pauseReason: "end",
        };
      }
      return { ...state, cursor: next };
    }
  }
}

function seek(state: ReplayPlaybackState, cursor: number): ReplayPlaybackState {
  const next = clamp(cursor, 1, state.totalBars);
  return {
    ...state,
    status: next >= state.totalBars ? "completed" : "paused",
    cursor: next,
    pauseReason: next >= state.totalBars ? "end" : "manual",
    decisionPaused: next >= state.decisionCursor,
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
