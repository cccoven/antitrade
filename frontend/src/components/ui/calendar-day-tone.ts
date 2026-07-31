interface CalendarDayToneState {
  outside?: boolean
  selected?: boolean
  range_start?: boolean
  range_end?: boolean
  range_middle?: boolean
}

export function getCalendarDayToneClass(
  state: CalendarDayToneState
): string | undefined {
  if (
    state.outside &&
    !state.selected &&
    !state.range_start &&
    !state.range_end &&
    !state.range_middle
  ) {
    return "text-muted-foreground/60"
  }

  return undefined
}
