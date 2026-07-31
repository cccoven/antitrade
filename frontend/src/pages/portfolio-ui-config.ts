export const portfolioToolbarControlSizes = {
  primaryAction: "sm",
  secondaryAction: "sm",
  iconAction: "icon-sm",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
} as const;

export const portfolioFilterControlSizes = {
  input: "sm",
  select: "sm",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
  inputPlaceholderClassName: "placeholder:text-[length:var(--font-caption)]",
  selectPlaceholderClassName:
    "data-[placeholder]:text-[length:var(--font-caption)]",
  valueFontSize: "var(--font-ui)",
  valueFontWeight: 400,
} as const;

export const portfolioFormControlSizes = {
  input: "sm",
  textareaRows: 3,
  fontSize: "var(--font-ui)",
  fontWeight: 400,
  labelTextClassName: "text-caption text-muted-foreground",
  inputPlaceholderClassName: "placeholder:text-[length:var(--font-caption)]",
  selectPlaceholderClassName:
    "data-[placeholder]:text-[length:var(--font-caption)]",
} as const;

export const portfolioTableControlSizes = {
  rowAction: "icon-xs",
  headerTextClassName: "text-caption text-muted-foreground font-normal",
  cellFontSize: "var(--font-ui)",
  cellFontWeight: 400,
} as const;

export const portfolioSummarySizes = {
  labelTextClassName: "text-caption text-muted-foreground tracking-wide",
  heroValueTextClassName: "text-heading font-medium text-foreground",
  subValueTextClassName: "text-ui text-foreground",
  metaTextClassName: "text-caption text-muted-foreground",
} as const;

export const portfolioInlineTagClassName =
  "ml-1.5 text-caption text-muted-foreground";

export const DEFAULT_CURRENCY_OPTIONS = [
  "CNY",
  "USD",
  "HKD",
  "EUR",
  "JPY",
  "GBP",
  "AUD",
  "SGD",
] as const;
