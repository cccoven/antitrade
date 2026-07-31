import { useRef, useState } from "react";
import { ImagePlus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import ImageAnnotationDialog from "@/components/ImageAnnotationDialog";
import { authedAssetUrl, uploadAsset, type UploadedAsset, type TradeImage } from "@/api/client";
import { journalTradeFormControlSizes } from "@/pages/journal-ui-config";

type LocalTradeImage = UploadedAsset | TradeImage;

function assetId(image: LocalTradeImage): string {
  return "asset_id" in image ? image.asset_id : image.id;
}

export default function TradeImageUploader({
  images,
  onChange,
}: {
  images: LocalTradeImage[];
  onChange: (images: LocalTradeImage[]) => void;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<LocalTradeImage | null>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const uploaded: UploadedAsset[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await uploadAsset(file));
      }
      onChange([...images, ...uploaded]);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const removeImage = (id: string) => {
    onChange(images.filter((image) => assetId(image) !== id));
  };

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        className="hidden"
        onChange={(event) => handleFiles(event.target.files)}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-caption font-medium text-muted-foreground">
          {t("journal.screenshots")}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          style={{
            fontSize: journalTradeFormControlSizes.fontSize,
            fontWeight: journalTradeFormControlSizes.fontWeight,
          }}
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          <ImagePlus data-icon="inline-start" />
          {uploading ? t("journal.uploading") : t("journal.addScreenshot")}
        </Button>
      </div>
      {images.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {images.map((image) => {
            const id = assetId(image);
            return (
              <div
                key={id}
                className="group relative aspect-video overflow-hidden rounded-md border border-border bg-muted"
              >
                <button
                  type="button"
                  className="h-full w-full"
                  onClick={() => setPreview(image)}
                >
                  <img
                    src={authedAssetUrl(image.url)}
                    alt={image.original_name || t("journal.screenshot")}
                    className="h-full w-full object-cover"
                  />
                </button>
                <Button
                  type="button"
                  variant="destructive"
                  size="icon-xs"
                  className="absolute right-1 top-1 opacity-0 transition-opacity group-hover:opacity-100"
                  onClick={() => removeImage(id)}
                  aria-label={t("journal.removeScreenshot")}
                  title={t("journal.removeScreenshot")}
                >
                  <Trash2 />
                </Button>
              </div>
            );
          })}
        </div>
      )}
      <ImageAnnotationDialog
        assetId={preview ? assetId(preview) : null}
        image={preview}
        open={preview != null}
        onOpenChange={(open) => !open && setPreview(null)}
      />
    </div>
  );
}
