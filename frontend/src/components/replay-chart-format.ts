import type { Time } from "lightweight-charts";

function toTimestampMilliseconds(time: Time): number | null {
  if (typeof time === "number") return time * 1000;
  if (typeof time === "string") {
    const parsed = Date.parse(time);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return Date.UTC(time.year, time.month - 1, time.day);
}

export function formatReplayChartTime(
  time: Time,
  locale: string,
  timeZone: string,
): string {
  const milliseconds = toTimestampMilliseconds(time);
  if (milliseconds == null) return String(time);
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(milliseconds);
}

export function formatReplayChartTick(
  time: Time,
  tickMarkType: number,
  locale: string,
  timeZone: string,
): string {
  const milliseconds = toTimestampMilliseconds(time);
  if (milliseconds == null) return String(time);

  if (tickMarkType >= 3) {
    return new Intl.DateTimeFormat(locale, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone,
    }).format(milliseconds);
  }
  if (tickMarkType === 0) {
    return new Intl.DateTimeFormat(locale, {
      year: "numeric",
      timeZone,
    }).format(milliseconds);
  }
  if (tickMarkType === 1) {
    return new Intl.DateTimeFormat(locale, {
      month: "short",
      timeZone,
    }).format(milliseconds);
  }
  return new Intl.DateTimeFormat(locale, {
    month: "numeric",
    day: "numeric",
    timeZone,
  }).format(milliseconds);
}
