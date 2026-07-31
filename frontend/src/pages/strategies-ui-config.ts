import type { CSSProperties } from "react";

export const inputStyle: CSSProperties = { fontSize: "var(--font-ui)" };
export const captionStyle: CSSProperties = { fontSize: "var(--font-caption)" };
export const btnStyle: CSSProperties = { fontSize: "var(--font-ui)", fontWeight: 400 };

// Mirrors journal-ui-config.ts so the strategies top bar reads like /journal.
export const strategiesToolbarControlSizes = {
  primaryAction: "sm",
  secondaryAction: "sm",
  iconAction: "icon-sm",
  fontSize: "var(--font-ui)",
  fontWeight: 400,
} as const;

export const strategiesGalleryLayout = {
  gridClassName:
    "grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),320px))] justify-center gap-x-6 gap-y-5",
} as const;

export const strategiesCardDensity = {
  previewAspectClassName: "aspect-[2/1]",
  bodyClassName: "min-h-32 gap-3 p-3.5",
  titleClassName: "items-start gap-2 pr-7 text-ui font-medium leading-snug",
  tagListClassName: "gap-1.5",
  tagClassName: "rounded bg-muted px-1.5 py-0.5",
  footerClassName: "mt-auto border-t border-border/70 pt-3",
} as const;
