import test from "node:test";
import assert from "node:assert/strict";

import {
  strategiesCardDensity,
  strategiesGalleryLayout,
  strategiesToolbarControlSizes,
} from "../src/pages/strategies-ui-config.ts";

test("strategies toolbar actions stay on compact button sizes", () => {
  assert.deepEqual(strategiesToolbarControlSizes, {
    primaryAction: "sm",
    secondaryAction: "sm",
    iconAction: "icon-sm",
    fontSize: "var(--font-ui)",
    fontWeight: 400,
  });
});

test("strategies cards keep the compact gallery density", () => {
  assert.deepEqual(strategiesGalleryLayout, {
    gridClassName:
      "grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),300px))] justify-center gap-8",
  });

  assert.deepEqual(strategiesCardDensity, {
    previewAspectClassName: "aspect-[16/9]",
    previewTextClassName: "p-2.5 text-caption leading-snug",
    bodyClassName: "gap-2 px-2.5 py-2.5",
    titleClassName: "gap-1.5 text-ui",
    tagListClassName: "gap-1.5",
    tagClassName: "rounded bg-muted px-1.5 py-0.5",
  });
});
