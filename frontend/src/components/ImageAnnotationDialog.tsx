import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/Toast";
import {
  authedAssetUrl,
  fetchImageAnnotations,
  replaceImageAnnotations,
  type ImageAnnotation,
} from "@/api/client";
import { journalTradeFormControlSizes } from "@/pages/journal-ui-config";
import {
  getContainedImageRect,
  getLoadedImageSize,
  getImageSizeForAsset,
  getNormalizedImagePoint,
  type LoadedImageSize,
} from "@/components/image-annotations";
import { cn } from "@/lib/utils";

type PreviewImage = {
  url: string;
  original_name?: string | null;
};

interface DraftAnnotation {
  key: string;
  xRatio: number;
  yRatio: number;
  body: string;
}

function toDraft(annotation: ImageAnnotation): DraftAnnotation {
  return {
    key: annotation.id,
    xRatio: annotation.x_ratio,
    yRatio: annotation.y_ratio,
    body: annotation.body,
  };
}

export default function ImageAnnotationDialog({
  assetId,
  image,
  open,
  onOpenChange,
}: {
  assetId: string | null;
  image: PreviewImage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const noteRefs = useRef(new Map<string, HTMLTextAreaElement>());
  const [imageElement, setImageElement] = useState<HTMLImageElement | null>(null);
  const [stageElement, setStageElement] = useState<HTMLDivElement | null>(null);
  const [annotations, setAnnotations] = useState<DraftAnnotation[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [loadedImageSize, setLoadedImageSize] =
    useState<LoadedImageSize | null>(null);
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const controlStyle = {
    fontSize: journalTradeFormControlSizes.fontSize,
    fontWeight: journalTradeFormControlSizes.fontWeight,
  };

  useEffect(() => {
    if (!open || !assetId) return;
    let cancelled = false;
    setLoading(true);
    setDirty(false);
    setAnnotations([]);
    setSelectedKey(null);
    fetchImageAnnotations(assetId)
      .then((items) => {
        if (cancelled) return;
        const drafts = items.map(toDraft);
        setAnnotations(drafts);
        setSelectedKey(drafts[0]?.key ?? null);
      })
      .catch(() => {
        if (cancelled) return;
        setAnnotations([]);
        setSelectedKey(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assetId, open]);

  useEffect(() => {
    if (!open || !stageElement) return;
    const updateSize = () => {
      const rect = stageElement.getBoundingClientRect();
      setStageSize({ width: rect.width, height: rect.height });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(stageElement);
    return () => observer.disconnect();
  }, [open, stageElement]);

  useLayoutEffect(() => {
    if (!open || !imageElement) return;

    const syncLoadedImageSize = () => {
      const loadedSize = getLoadedImageSize(assetId, imageElement);
      if (loadedSize) setLoadedImageSize(loadedSize);
    };

    if (imageElement.complete) {
      syncLoadedImageSize();
      return;
    }

    imageElement.addEventListener("load", syncLoadedImageSize);
    return () =>
      imageElement.removeEventListener("load", syncLoadedImageSize);
  }, [assetId, imageElement, open]);

  const imageRect = useMemo(
    () => {
      const naturalSize = getImageSizeForAsset(loadedImageSize, assetId);
      return getContainedImageRect(
        stageSize.width,
        stageSize.height,
        naturalSize.width,
        naturalSize.height,
      );
    },
    [assetId, loadedImageSize, stageSize],
  );

  const focusNote = (key: string) => {
    window.requestAnimationFrame(() => noteRefs.current.get(key)?.focus());
  };

  const handleStageClick = (event: MouseEvent<HTMLDivElement>) => {
    if (!stageElement || loading || annotations.length >= 50) {
      if (annotations.length >= 50) {
        showToast(t("journal.annotations.maxReached"), "error");
      }
      return;
    }
    const bounds = stageElement.getBoundingClientRect();
    const stageImage = stageElement.querySelector("img");
    const currentImageRect = getContainedImageRect(
      bounds.width,
      bounds.height,
      stageImage?.naturalWidth ?? 0,
      stageImage?.naturalHeight ?? 0,
    );
    const point = getNormalizedImagePoint(
      event.clientX - bounds.left,
      event.clientY - bounds.top,
      currentImageRect,
    );
    if (!point) return;

    const key = crypto.randomUUID();
    setAnnotations((current) => [
      ...current,
      {
        key,
        xRatio: point.xRatio,
        yRatio: point.yRatio,
        body: "",
      },
    ]);
    setSelectedKey(key);
    setDirty(true);
    focusNote(key);
  };

  const updateBody = (key: string, body: string) => {
    setAnnotations((current) =>
      current.map((item) => (item.key === key ? { ...item, body } : item)),
    );
    setDirty(true);
  };

  const removeAnnotation = (key: string) => {
    setAnnotations((current) => {
      const index = current.findIndex((item) => item.key === key);
      const next = current.filter((item) => item.key !== key);
      if (selectedKey === key) {
        setSelectedKey(next[Math.min(index, next.length - 1)]?.key ?? null);
      }
      return next;
    });
    setDirty(true);
  };

  const handleSave = async () => {
    if (!assetId || annotations.some((item) => !item.body.trim())) return;
    setSaving(true);
    try {
      const saved = await replaceImageAnnotations(
        assetId,
        annotations.map((item) => ({
          x_ratio: item.xRatio,
          y_ratio: item.yRatio,
          body: item.body.trim(),
        })),
      );
      const drafts = saved.map(toDraft);
      const selectedIndex = annotations.findIndex(
        (item) => item.key === selectedKey,
      );
      setAnnotations(drafts);
      setSelectedKey(
        drafts[Math.max(0, selectedIndex)]?.key ?? drafts[0]?.key ?? null,
      );
      setDirty(false);
      showToast(t("journal.annotations.saved"), "success");
    } catch {
      // The API client already shows normalized user-facing error copy.
    } finally {
      setSaving(false);
    }
  };

  const hasEmptyNote = annotations.some((item) => !item.body.trim());

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/72 backdrop-blur-[4px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className="fixed inset-[12px] z-50 grid min-h-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden rounded-[20px] border border-border bg-popover text-popover-foreground shadow-[var(--shadow-lg)] outline-none md:inset-[18px] md:rounded-[28px]"
        >
          <DialogPrimitive.Title className="sr-only">
            {t("journal.annotations.title")}
          </DialogPrimitive.Title>
          <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <div className="min-w-0">
              <div className="truncate text-subheading font-semibold text-foreground">
                {image?.original_name || t("journal.screenshot")}
              </div>
              <div className="text-caption text-muted-foreground">
                {t("journal.annotations.clickHint")}
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              style={controlStyle}
              onClick={() => onOpenChange(false)}
              aria-label={t("journal.close")}
            >
              <X />
            </Button>
          </header>

          <div className="grid min-h-0 grid-rows-[minmax(280px,1fr)_minmax(220px,42vh)] md:grid-cols-[minmax(0,1fr)_360px] md:grid-rows-1">
            <div
              ref={setStageElement}
              data-testid="image-annotation-stage"
              className="relative min-h-0 cursor-crosshair overflow-hidden bg-black/80"
              onClick={handleStageClick}
            >
              {image ? (
                <img
                  ref={setImageElement}
                  src={authedAssetUrl(image.url)}
                  alt={image.original_name ?? ""}
                  className="pointer-events-none absolute inset-0 h-full w-full select-none object-contain"
                  draggable={false}
                />
              ) : null}

              {annotations.map((annotation, index) => (
                <button
                  key={annotation.key}
                  type="button"
                  className={cn(
                    "absolute z-10 flex size-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 text-micro font-semibold shadow-md transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selectedKey === annotation.key
                      ? "border-primary-foreground bg-primary text-primary-foreground"
                      : "border-background bg-foreground text-background",
                  )}
                  style={{
                    left: imageRect.left + annotation.xRatio * imageRect.width,
                    top: imageRect.top + annotation.yRatio * imageRect.height,
                    fontSize: "var(--font-micro)",
                  }}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedKey(annotation.key);
                    focusNote(annotation.key);
                  }}
                  aria-label={t("journal.annotations.marker", {
                    number: index + 1,
                  })}
                >
                  {index + 1}
                </button>
              ))}

              {loading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-ui text-white/70">
                  {t("journal.annotations.loading")}
                </div>
              ) : null}
            </div>

            <aside className="flex min-h-0 flex-col border-t border-border bg-popover md:border-l md:border-t-0">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <span className="text-subheading font-semibold">
                  {t("journal.annotations.notes")}
                </span>
                <span className="text-caption text-muted-foreground">
                  {annotations.length}/50
                </span>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {!loading && annotations.length === 0 ? (
                  <div className="flex h-full min-h-32 items-center justify-center text-center text-caption text-muted-foreground">
                    {t("journal.annotations.empty")}
                  </div>
                ) : null}

                <div className="flex flex-col gap-2">
                  {annotations.map((annotation, index) => (
                    <div
                      key={annotation.key}
                      className={cn(
                        "grid grid-cols-[28px_minmax(0,1fr)_28px] gap-2 rounded-[12px] border p-2 transition-colors",
                        selectedKey === annotation.key
                          ? "border-primary bg-primary/5"
                          : "border-border bg-card",
                      )}
                      onClick={() => setSelectedKey(annotation.key)}
                    >
                      <span className="flex size-7 items-center justify-center rounded-full bg-foreground text-micro font-semibold text-background">
                        {index + 1}
                      </span>
                      <Textarea
                        ref={(element) => {
                          if (element) noteRefs.current.set(annotation.key, element);
                          else noteRefs.current.delete(annotation.key);
                        }}
                        value={annotation.body}
                        rows={3}
                        className="min-h-20 resize-none text-ui"
                        style={controlStyle}
                        placeholder={t("journal.annotations.placeholder")}
                        onFocus={() => setSelectedKey(annotation.key)}
                        onChange={(event) =>
                          updateBody(annotation.key, event.target.value)
                        }
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        style={controlStyle}
                        className="text-muted-foreground hover:text-destructive"
                        onClick={(event) => {
                          event.stopPropagation();
                          removeAnnotation(annotation.key);
                        }}
                        aria-label={t("journal.annotations.delete")}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              {hasEmptyNote ? (
                <div className="px-4 pb-2 text-caption text-destructive">
                  {t("journal.annotations.emptyNote")}
                </div>
              ) : null}
              <footer className="flex gap-2 border-t border-border p-3">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  style={controlStyle}
                  className="flex-1"
                  onClick={() => onOpenChange(false)}
                  disabled={saving}
                >
                  {t("journal.close")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  style={controlStyle}
                  className="flex-1"
                  onClick={() => void handleSave()}
                  disabled={loading || saving || hasEmptyNote || !dirty}
                >
                  {saving
                    ? t("journal.annotations.saving")
                    : t("journal.annotations.save")}
                </Button>
              </footer>
            </aside>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
