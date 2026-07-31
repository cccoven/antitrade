import type {
  MarketHoursItem,
  LocalizedMarketText,
  MarketHoursSession,
} from "@/api/client";

export function localized(value: LocalizedMarketText | null | undefined, language: string) {
  if (!value) return "";
  return language === "zh" ? value.zh : value.en;
}

export function formatClock(date: Date, timeZone: string, locale: string) {
  const parts = new Intl.DateTimeFormat(locale, {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "00";
  return { time: `${value("hour")}:${value("minute")}`, seconds: value("second") };
}

export function formatDate(date: Date, timeZone: string, locale: string) {
  return new Intl.DateTimeFormat(locale, {
    timeZone,
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatOffset(date: Date, timeZone: string, locale: string) {
  const parts = new Intl.DateTimeFormat(locale, {
    timeZone,
    timeZoneName: "shortOffset",
  }).formatToParts(date);
  return parts.find((part) => part.type === "timeZoneName")?.value ?? timeZone;
}

export function formatSessionTime(value: string, timeZone: string, locale: string) {
  return new Intl.DateTimeFormat(locale, {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function formatCountdown(value: string | null, now: Date, language: string) {
  if (!value) return "—";
  const minutes = Math.max(0, Math.floor((new Date(value).getTime() - now.getTime()) / 60_000));
  if (minutes < 1) return language === "zh" ? "不到 1 分钟" : "less than 1 min";
  const days = Math.floor(minutes / 1_440);
  const hours = Math.floor((minutes % 1_440) / 60);
  const rest = minutes % 60;
  if (language === "zh") {
    return [days ? `${days}天` : "", hours ? `${hours}小时` : "", rest ? `${rest}分钟` : ""]
      .filter(Boolean)
      .join(" ");
  }
  return [days ? `${days}d` : "", hours ? `${hours}h` : "", rest ? `${rest}m` : ""]
    .filter(Boolean)
    .join(" ");
}

export function marketStateAt(item: MarketHoursItem, now: Date): MarketHoursItem["state"] {
  const nowMs = now.getTime();
  const active = item.sessions.find((session) => {
    const start = new Date(session.start_at).getTime();
    const end = new Date(session.end_at).getTime();
    return start <= nowMs && nowMs < end;
  });
  return active?.kind ?? "closed";
}

export function timelineStyle(
  startAt: string,
  endAt: string,
  windowStartAt: string,
  windowEndAt: string,
) {
  const windowStart = new Date(windowStartAt).getTime();
  const windowEnd = new Date(windowEndAt).getTime();
  const start = Math.max(windowStart, new Date(startAt).getTime());
  const end = Math.min(windowEnd, new Date(endAt).getTime());
  if (end <= start || windowEnd <= windowStart) return null;
  return {
    left: `${((start - windowStart) / (windowEnd - windowStart)) * 100}%`,
    width: `${((end - start) / (windowEnd - windowStart)) * 100}%`,
  };
}

export function nowPosition(now: Date, windowStartAt: string, windowEndAt: string) {
  const start = new Date(windowStartAt).getTime();
  const end = new Date(windowEndAt).getTime();
  return Math.min(100, Math.max(0, ((now.getTime() - start) / (end - start)) * 100));
}

export function visibleSessionLabel(
  session: MarketHoursSession,
  timeZone: string,
  locale: string,
) {
  return `${formatSessionTime(session.start_at, timeZone, locale)}–${formatSessionTime(session.end_at, timeZone, locale)}`;
}

export const countryMarker: Record<string, string> = {
  US: "🇺🇸",
  GB: "🇬🇧",
  EU: "🇪🇺",
  DE: "🇩🇪",
  CN: "🇨🇳",
  HK: "🇭🇰",
  JP: "🇯🇵",
  KR: "🇰🇷",
  SG: "🇸🇬",
  AU: "🇦🇺",
  FX: "FX",
  XAU: "Au",
  XAG: "Ag",
};
