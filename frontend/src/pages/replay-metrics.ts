export interface ReplayMetricBar {
  high: number;
  low: number;
}

export interface ReplayExcursion {
  mfe: number;
  mae: number;
}

export function calculateReplayExcursion({
  bars,
  openIndex,
  heldEndIndex,
  openPrice,
  direction,
}: {
  bars: ReplayMetricBar[];
  openIndex: number;
  heldEndIndex: number;
  openPrice: number;
  direction: "long" | "short";
}): ReplayExcursion | null {
  const held = bars.slice(openIndex, heldEndIndex + 1);
  if (!held.length) return null;

  const high = Math.max(...held.map((bar) => bar.high));
  const low = Math.min(...held.map((bar) => bar.low));
  const isLong = direction === "long";

  return {
    mfe: Math.max(0, isLong ? high - openPrice : openPrice - low),
    mae: Math.min(0, isLong ? low - openPrice : openPrice - high),
  };
}
