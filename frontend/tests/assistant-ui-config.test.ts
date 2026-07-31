import assert from "node:assert/strict";
import test from "node:test";
import {
  assistantHistoryPanel,
  clampAssistantHistoryWidth,
} from "../src/pages/assistant-ui-config.ts";

test("assistant history width stays within the supported range", () => {
  assert.equal(
    clampAssistantHistoryWidth(assistantHistoryPanel.minWidth - 100),
    assistantHistoryPanel.minWidth,
  );
  assert.equal(clampAssistantHistoryWidth(300.4), 300);
  assert.equal(
    clampAssistantHistoryWidth(assistantHistoryPanel.maxWidth + 100),
    assistantHistoryPanel.maxWidth,
  );
  assert.equal(
    clampAssistantHistoryWidth(Number.NaN),
    assistantHistoryPanel.defaultWidth,
  );
});
