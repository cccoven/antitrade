import i18n from "@/i18n";

export function formatPct(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return "-";
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const hLabel = i18n.t("journal.duration.h");
  const mLabel = i18n.t("journal.duration.min");
  const sLabel = i18n.t("journal.duration.sec");
  if (h > 0) return `${h}${hLabel} ${m}${mLabel} ${sec}${sLabel}`;
  if (m > 0) return `${m}${mLabel} ${sec}${sLabel}`;
  return `${sec}${sLabel}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function formatInt(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${Math.round(value)}`;
}

export function pnlColor(value: number): string {
  if (value > 0) return "var(--success)";
  if (value < 0) return "var(--danger)";
  return "var(--text-primary)";
}
