export function applyJournalSymbolDraft(draft: string): string {
  return draft.trim();
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function toDatetimeLocalValue(date: Date, hours: number, minutes: number): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(hours)}:${pad(minutes)}`;
}

/**
 * Convert a datetime-local string ("YYYY-MM-DDTHH:mm" in local time) into a
 * UTC ISO string the backend can lexicographically compare against the
 * Z-suffixed open_time values stored in SQLite.
 */
export function journalLocalDateTimeToIso(value: string): string {
  if (!value) return value;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toISOString();
}

export function buildJournalTradeQueryParams(
  filterSymbol: string,
  filterDirection: string,
  filterPositionStatus: string,
  dateFrom = "",
  dateTo = "",
  limit?: number,
  offset?: number
): Record<string, string | number> {
  const params: Record<string, string | number> = {};

  if (filterSymbol) {
    params.symbol = filterSymbol;
  }

  if (filterDirection && filterDirection !== "all") {
    params.direction = filterDirection;
  }

  if (filterPositionStatus && filterPositionStatus !== "all") {
    params.position_status = filterPositionStatus;
  }

  if (dateFrom) {
    params.date_from = journalLocalDateTimeToIso(dateFrom);
  }

  if (dateTo) {
    params.date_to = journalLocalDateTimeToIso(dateTo);
  }

  if (limit !== undefined) {
    params.limit = limit;
  }

  if (offset !== undefined) {
    params.offset = offset;
  }

  return params;
}

export function buildJournalDayRange(day: Date): {
  dateFrom: string;
  dateTo: string;
} {
  return {
    dateFrom: toDatetimeLocalValue(day, 0, 0),
    dateTo: toDatetimeLocalValue(day, 23, 59),
  };
}

export function getSelectedJournalDay(
  dateFrom: string,
  dateTo: string
): Date | null {
  if (!dateFrom || !dateTo) {
    return null;
  }

  const fromMatch = dateFrom.match(/^(\d{4}-\d{2}-\d{2})T00:00$/);
  const toMatch = dateTo.match(/^(\d{4}-\d{2}-\d{2})T23:59$/);
  if (!fromMatch || !toMatch || fromMatch[1] !== toMatch[1]) {
    return null;
  }

  const selected = new Date(`${fromMatch[1]}T00:00:00`);
  return Number.isNaN(selected.getTime()) ? null : selected;
}
