import type { MarketHoursGroup, MarketHoursSessionKind } from "@/api/client";

export const marketHoursControlSizes = {
  refreshAction: "icon-sm",
  buttonStyle: { fontSize: "var(--font-ui)", fontWeight: 400 },
  inputStyle: { fontSize: "var(--font-ui)" },
  filterTabClassName:
    "h-7 rounded-none border-b-2 border-transparent px-2.5 font-normal text-muted-foreground hover:bg-transparent hover:text-foreground data-[state=on]:border-[var(--market-info)] data-[state=on]:!bg-transparent data-[state=on]:text-foreground",
} as const;

export const referenceZones = [
  { timezone: "America/New_York", zh: "纽约", en: "New York" },
  { timezone: "Europe/London", zh: "伦敦", en: "London" },
  { timezone: "Asia/Dubai", zh: "迪拜", en: "Dubai" },
  { timezone: "Asia/Shanghai", zh: "北京", en: "Beijing" },
  { timezone: "Asia/Tokyo", zh: "东京", en: "Tokyo" },
] as const;

export const marketGroups: Array<{ value: "all" | MarketHoursGroup; labelKey: string }> = [
  { value: "all", labelKey: "marketHours.group.all" },
  { value: "equities", labelKey: "marketHours.group.equities" },
  { value: "spot_forex", labelKey: "marketHours.group.spot_forex" },
  { value: "futures", labelKey: "marketHours.group.futures" },
];

export const groupOrder: MarketHoursGroup[] = ["equities", "spot_forex", "futures"];

export const sessionTone: Record<MarketHoursSessionKind, string> = {
  main: "border-primary/60 bg-primary/45",
  night: "border-violet-500/50 bg-violet-500/35",
  pre: "border-sky-500/50 bg-sky-500/30",
  after: "border-amber-500/50 bg-amber-500/30",
};
