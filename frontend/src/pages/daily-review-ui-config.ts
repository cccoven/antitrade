export const dailyReviewControlSizes = {
  primaryAction: "sm",
  secondaryAction: "sm",
  iconAction: "icon-sm",
  input: "sm",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
  titleTextClassName: "text-subheading",
  bodyTextClassName: "text-ui",
  metaTextClassName: "text-caption",
} as const;

export const dailyReviewControlStyle = {
  fontSize: dailyReviewControlSizes.fontSize,
  fontWeight: dailyReviewControlSizes.fontWeight,
} as const;
