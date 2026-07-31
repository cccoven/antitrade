export const journalToolbarControlSizes = {
  iconAction: "icon-sm",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
} as const;

export const journalFilterControlSizes = {
  input: "sm",
  select: "sm",
  dateTimeButton: "sm",
  clearTimeAction: "icon-xs",
  searchAction: "icon-xs",
  fieldLabelTextClassName: "text-caption text-muted-foreground",
  inputPlaceholderClassName: "placeholder:text-[length:var(--font-caption)]",
  selectPlaceholderClassName:
    "data-[placeholder]:text-[length:var(--font-caption)]",
  dateTimePlaceholderFontSize: "var(--font-caption)",
  dateTimeValueFontSize: "var(--font-ui)",
  dateTimeValueFontWeight: 400,
  dateTimeTimeInputClassName: "h-8",
  valueFontSize: "var(--font-ui)",
  valueFontWeight: 400,
} as const;

export const journalStatsControlSizes = {
  rangeToggle: "sm",
  dimensionToggle: "sm",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
} as const;

export const journalCalendarControlSizes = {
  monthPickerAction: "sm",
  monthPickerContentWidthClassName: "w-[260px]",
  monthPickerGridClassName: "grid grid-cols-3 gap-2",
  monthPickerMetaTextClassName: "text-caption",
  monthPickerFontSize: "var(--font-ui)",
  monthPickerFontWeight: 400,
  dayCellHeightClassName: "min-h-[92px]",
  dayPositiveToneClassName:
    "border-[color-mix(in_srgb,var(--success)_28%,var(--border))] bg-[color-mix(in_srgb,var(--success)_9%,var(--card))] dark:border-[color-mix(in_srgb,var(--success)_64%,var(--border))] dark:bg-[color-mix(in_srgb,var(--success)_48%,var(--chip-bg))]",
  dayNegativeToneClassName:
    "border-[color-mix(in_srgb,var(--danger)_28%,var(--border))] bg-[color-mix(in_srgb,var(--danger)_9%,var(--card))] dark:border-[color-mix(in_srgb,var(--danger)_64%,var(--border))] dark:bg-[color-mix(in_srgb,var(--danger)_48%,var(--chip-bg))]",
  dayGridSpacingClassName: "[border-spacing:6px_6px]",
  dayValueTextClassName: "text-subheading",
  weekMetaBadgeSurfaceClassName: "bg-[var(--accent-soft)]",
  weekTitleTextClassName: "text-caption",
  weekValueTextClassName: "text-subheading",
  weekMetaTextClassName: "text-caption",
} as const;

export const journalTradeFormControlSizes = {
  toggle: "sm",
  dateTimeButton: "sm",
  timeInputClassName: "h-8",
  notesRows: 4,
  fontSize: "var(--font-ui)",
  fontWeight: 400,
  inputPlaceholderClassName: "placeholder:text-[length:var(--font-caption)]",
  dateTimePlaceholderFontSize: "var(--font-caption)",
  fieldValueFontSize: "var(--font-ui)",
  fieldValueFontWeight: 400,
  dateTimeCalendarFontSize: "var(--font-ui)",
  dateTimeCalendarMetaFontSize: "var(--font-caption)",
  dateTimeTimeInputFontSize: "var(--font-ui)",
  dateTimeTimeInputFontWeight: 400,
} as const;

export const journalTableControlSizes = {
  rowAction: "icon-xs",
  directionBadgeText: "text-caption",
  tagBadgeSurfaceClassName: "bg-[var(--accent-soft)]",
  tagBadgeText: "text-caption",
} as const;

export const journalRecognitionControlSizes = {
  primaryAction: "sm",
  secondaryAction: "sm",
  retryAction: "xs",
  titleTextClassName: "text-subheading",
  bodyTextClassName: "text-ui",
  metaTextClassName: "text-caption",
  buttonFontSize: "var(--font-ui)",
  buttonFontWeight: 400,
  tableHeaderFontSize: "var(--font-caption)",
} as const;
