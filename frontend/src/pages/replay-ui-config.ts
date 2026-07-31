// Page-local UI sizing for the Replay page.
// Mirrors patterns in journal-ui-config.ts and backtest-ui-config.ts.

export const replayControlSizes = {
  primaryAction: "sm" as const,
  iconAction: "icon-sm" as const,
  toggle: "sm" as const,
  select: "sm" as const,
  fontSize: "var(--font-ui)",
  fontWeight: 500,
  captionFontSize: "var(--font-caption)",
};

export const replayPageStyles = {
  inputStyle: { fontSize: "var(--font-ui)" },
  btnStyle: { fontSize: "var(--font-ui)", fontWeight: 500 },
  badgeStyle: { fontSize: "var(--font-caption)" },
};

export const REPLAY_INTERVAL_OPTIONS: readonly { value: string; key: string }[] = [
  { value: "auto", key: "replay.intervalAuto" },
  { value: "1", key: "replay.interval.1" },
  { value: "5", key: "replay.interval.5" },
  { value: "15", key: "replay.interval.15" },
  { value: "60", key: "replay.interval.60" },
  { value: "240", key: "replay.interval.240" },
  { value: "D", key: "replay.interval.D" },
] as const;

export const REPLAY_WINDOW_OPTIONS: readonly { value: "compact" | "standard" | "full"; key: string }[] = [
  { value: "compact", key: "replay.window.compact" },
  { value: "standard", key: "replay.window.standard" },
  { value: "full", key: "replay.window.full" },
] as const;

export const REPLAY_SPEED_OPTIONS: readonly number[] = [0.5, 1, 2, 4] as const;

export const REPLAY_PREFS_STORAGE_KEY = "replay-prefs";
