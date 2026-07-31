export function formatLocalDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function parseLocalDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function localDayRangeIso(date: string): {
  date_from: string;
  date_to: string;
} {
  const d = parseLocalDate(date);
  const from = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0);
  const to = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
  return { date_from: from.toISOString(), date_to: to.toISOString() };
}
