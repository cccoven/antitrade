export const radarControlSizes = {
  filter: "sm",
  iconAction: "icon-sm",
  bookmarkAction: "icon-xs",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
  tabStyle: { fontSize: "var(--font-caption)", lineHeight: 1.2 },
  titleTextClassName: "text-subheading",
  metaTextClassName: "text-caption",
  bodyTextClassName: "text-ui",
} as const;

export const RADAR_CATEGORIES = [
  "all",
  "crypto",
  "forex",
  "macro",
  "general",
] as const;

export type RadarCategory = (typeof RADAR_CATEGORIES)[number];
