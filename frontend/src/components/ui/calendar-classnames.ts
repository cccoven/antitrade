import { cn } from "@/lib/utils"

type CalendarClassNames = Record<string, string | undefined>

const calendarStructuralClassNames: CalendarClassNames = {
  caption_label: "select-none",
  dropdowns: "",
  weekday: "flex-1 rounded-md select-none",
  week_number: "select-none",
}

export function mergeCalendarClassNames(
  overrides?: CalendarClassNames
): CalendarClassNames {
  const merged: CalendarClassNames = { ...(overrides ?? {}) }

  for (const [key, base] of Object.entries(calendarStructuralClassNames)) {
    merged[key] = cn(base, overrides?.[key])
  }

  return merged
}
