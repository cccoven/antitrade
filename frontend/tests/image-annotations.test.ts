import test from "node:test";
import assert from "node:assert/strict";

import {
  getContainedImageRect,
  getLoadedImageSize,
  getImageSizeForAsset,
  getNormalizedImagePoint,
} from "../src/components/image-annotations";

test("contained image rect preserves aspect ratio and centers letterboxing", () => {
  assert.deepEqual(getContainedImageRect(1000, 600, 1000, 1000), {
    left: 200,
    top: 0,
    width: 600,
    height: 600,
  });

  assert.deepEqual(getContainedImageRect(800, 800, 1600, 900), {
    left: 0,
    top: 175,
    width: 800,
    height: 450,
  });
});

test("pointer coordinates are normalized against only the visible image", () => {
  const rect = getContainedImageRect(1000, 600, 1000, 1000);

  assert.deepEqual(getNormalizedImagePoint(500, 300, rect), {
    xRatio: 0.5,
    yRatio: 0.5,
  });
  assert.equal(getNormalizedImagePoint(100, 300, rect), null);
  assert.equal(getNormalizedImagePoint(900, 300, rect), null);
});

test("loaded image size only applies to the asset that produced it", () => {
  const loadedImage = {
    assetId: "asset-a",
    width: 2302,
    height: 964,
  };

  assert.deepEqual(getImageSizeForAsset(loadedImage, "asset-a"), {
    width: 2302,
    height: 964,
  });
  assert.deepEqual(getImageSizeForAsset(loadedImage, "asset-b"), {
    width: 0,
    height: 0,
  });
});

test("an already-complete cached image exposes its natural size immediately", () => {
  assert.deepEqual(
    getLoadedImageSize("asset-a", {
      complete: true,
      naturalWidth: 2302,
      naturalHeight: 964,
    }),
    {
      assetId: "asset-a",
      width: 2302,
      height: 964,
    },
  );
  assert.equal(
    getLoadedImageSize("asset-a", {
      complete: false,
      naturalWidth: 0,
      naturalHeight: 0,
    }),
    null,
  );
});
