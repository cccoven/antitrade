import test from "node:test";
import assert from "node:assert/strict";

import {
  journalCalendarControlSizes,
  journalFilterControlSizes,
  journalRecognitionControlSizes,
  journalStatsControlSizes,
  journalTableControlSizes,
  journalToolbarControlSizes,
  journalTradeFormControlSizes,
} from "../src/pages/journal-ui-config.ts";

test("journal toolbar actions stay on compact button sizes", () => {
  assert.deepEqual(journalToolbarControlSizes, {
    primaryAction: "sm",
    secondaryAction: "sm",
    iconAction: "icon-sm",
    fontSize: "var(--font-ui)",
    fontWeight: 400,
  });
});

test("journal filters and stats use compact control sizing", () => {
  assert.deepEqual(journalFilterControlSizes, {
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
  });
  assert.deepEqual(journalStatsControlSizes, {
    rangeToggle: "sm",
    dimensionToggle: "sm",
    fontSize: "var(--font-ui)",
    fontWeight: 400,
  });
  assert.deepEqual(journalCalendarControlSizes, {
    monthPickerAction: "sm",
    monthPickerContentWidthClassName: "w-[260px]",
    monthPickerGridClassName: "grid grid-cols-3 gap-2",
    monthPickerMetaTextClassName: "text-caption",
    monthPickerFontSize: "var(--font-ui)",
    monthPickerFontWeight: 400,
    dayCellHeightClassName: "min-h-[92px]",
    dayPositiveToneClassName:
      "border-[color-mix(in_srgb,var(--success)_64%,var(--border))] bg-[color-mix(in_srgb,var(--success)_48%,var(--chip-bg))]",
    dayNegativeToneClassName:
      "border-[color-mix(in_srgb,var(--danger)_64%,var(--border))] bg-[color-mix(in_srgb,var(--danger)_48%,var(--chip-bg))]",
    dayGridSpacingClassName: "[border-spacing:6px_6px]",
    dayValueTextClassName: "text-subheading",
    weekMetaBadgeSurfaceClassName: "bg-[var(--accent-soft)]",
    weekTitleTextClassName: "text-caption",
    weekValueTextClassName: "text-subheading",
    weekMetaTextClassName: "text-caption",
  });
});

test("journal form and table controls keep dense defaults", () => {
  assert.deepEqual(journalTradeFormControlSizes, {
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
  });
  assert.deepEqual(journalTableControlSizes, {
    rowAction: "icon-xs",
    directionBadgeText: "text-caption",
    tagBadgeSurfaceClassName: "bg-[var(--accent-soft)]",
    tagBadgeText: "text-caption",
  });
  assert.deepEqual(journalRecognitionControlSizes, {
    primaryAction: "sm",
    secondaryAction: "sm",
    retryAction: "xs",
    titleTextClassName: "text-subheading",
    bodyTextClassName: "text-ui",
    metaTextClassName: "text-caption",
    buttonFontSize: "var(--font-ui)",
    buttonFontWeight: 400,
    tableHeaderFontSize: "var(--font-caption)",
  });
});
