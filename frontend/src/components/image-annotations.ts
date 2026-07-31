export interface ContainedImageRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface LoadedImageSize {
  assetId: string;
  width: number;
  height: number;
}

interface ImageLoadState {
  complete: boolean;
  naturalWidth: number;
  naturalHeight: number;
}

export function getLoadedImageSize(
  assetId: string | null,
  image: ImageLoadState | null,
): LoadedImageSize | null {
  if (
    !assetId ||
    !image?.complete ||
    image.naturalWidth <= 0 ||
    image.naturalHeight <= 0
  ) {
    return null;
  }
  return {
    assetId,
    width: image.naturalWidth,
    height: image.naturalHeight,
  };
}

export function getImageSizeForAsset(
  loadedImage: LoadedImageSize | null,
  assetId: string | null,
): { width: number; height: number } {
  if (!loadedImage || loadedImage.assetId !== assetId) {
    return { width: 0, height: 0 };
  }
  return { width: loadedImage.width, height: loadedImage.height };
}

export function getContainedImageRect(
  containerWidth: number,
  containerHeight: number,
  naturalWidth: number,
  naturalHeight: number,
): ContainedImageRect {
  if (
    containerWidth <= 0 ||
    containerHeight <= 0 ||
    naturalWidth <= 0 ||
    naturalHeight <= 0
  ) {
    return { left: 0, top: 0, width: 0, height: 0 };
  }

  const scale = Math.min(
    containerWidth / naturalWidth,
    containerHeight / naturalHeight,
  );
  const width = naturalWidth * scale;
  const height = naturalHeight * scale;
  return {
    left: (containerWidth - width) / 2,
    top: (containerHeight - height) / 2,
    width,
    height,
  };
}

export function getNormalizedImagePoint(
  x: number,
  y: number,
  rect: ContainedImageRect,
): { xRatio: number; yRatio: number } | null {
  if (
    rect.width <= 0 ||
    rect.height <= 0 ||
    x < rect.left ||
    x > rect.left + rect.width ||
    y < rect.top ||
    y > rect.top + rect.height
  ) {
    return null;
  }

  return {
    xRatio: (x - rect.left) / rect.width,
    yRatio: (y - rect.top) / rect.height,
  };
}
