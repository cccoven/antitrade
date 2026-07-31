import { startOfMonth } from "date-fns";

export function toJournalMonthKey(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

export function buildJournalCalendarYearOptions(
  activeMonth: Date,
  pastYears = 5,
  futureYears = 1
): number[] {
  const currentYear = activeMonth.getFullYear();
  const years: number[] = [];

  for (
    let year = currentYear - pastYears;
    year <= currentYear + futureYears;
    year += 1
  ) {
    years.push(year);
  }

  return years;
}

export function setJournalCalendarMonth(
  activeMonth: Date,
  year: number,
  monthIndex: number
): Date {
  return startOfMonth(new Date(year, monthIndex, 1, activeMonth.getHours(), activeMonth.getMinutes()));
}
