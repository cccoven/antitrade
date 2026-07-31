import test from "node:test";
import assert from "node:assert/strict";

import {
  chartsAnalysisDrawerControlSizes,
  chartsPanelControlSizes,
  chartsSymbolPickerControlSizes,
  chartsToolbarControlSizes,
} from "../src/pages/charts-ui-config";

test("charts toolbar controls stay aligned with journal-sized actions", () => {
  assert.deepEqual(chartsToolbarControlSizes, {
    select: "sm",
    iconAction: "icon-sm",
    fontSize: "var(--font-ui)",
    fontWeight: 400,
    labelTextClassName: "text-ui",
  });
});

test("charts symbol picker keeps compact trigger, search, and option typography", () => {
  assert.deepEqual(chartsSymbolPickerControlSizes, {
    trigger: "sm",
    triggerFontSize: "var(--font-ui)",
    triggerFontWeight: 400,
    searchInputClassName:
      "h-8 border-0 px-0 py-0 text-[length:var(--font-ui)] shadow-none focus-visible:ring-0",
    searchPlaceholderClassName:
      "placeholder:text-[length:var(--font-caption)]",
    groupLabelTextClassName: "text-caption",
    optionTextClassName: "text-ui",
    emptyTextClassName: "text-ui",
  });
});

test("charts panel and drawer actions use the shared compact control scale", () => {
  assert.deepEqual(chartsPanelControlSizes, {
    titleTextClassName: "text-ui",
    titleFontWeight: 600,
    analyzeAction: "icon-xs",
    removeAction: "icon-xs",
  });

  assert.deepEqual(chartsAnalysisDrawerControlSizes, {
    primaryAction: "sm",
    secondaryAction: "sm",
    titleTextClassName: "text-subheading",
    metaTextClassName: "text-caption",
    bodyTextClassName: "text-ui",
    buttonFontSize: "var(--font-ui)",
    buttonFontWeight: 400,
  });
});
