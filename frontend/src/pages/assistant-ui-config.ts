export const assistantControlSizes = {
  primaryAction: "sm",
  iconAction: "icon-sm",
  rowAction: "icon-xs",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
} as const;

export const assistantInputStyle = {
  fontSize: assistantControlSizes.fontSize,
  fontWeight: assistantControlSizes.fontWeight,
} as const;

export const assistantToolbarStyle = {
  fontSize: "var(--font-caption)",
  fontWeight: assistantControlSizes.fontWeight,
} as const;

export const assistantHistoryPanel = {
  storageKey: "antitrade.assistant.historyWidth",
  collapsedStorageKey: "antitrade.assistant.historyCollapsed",
  defaultWidth: 240,
  collapsedWidth: 48,
  minWidth: 208,
  maxWidth: 420,
  keyboardStep: 16,
} as const;

export function clampAssistantHistoryWidth(width: number): number {
  if (!Number.isFinite(width)) return assistantHistoryPanel.defaultWidth;
  return Math.min(
    assistantHistoryPanel.maxWidth,
    Math.max(assistantHistoryPanel.minWidth, Math.round(width)),
  );
}
