import { Dialog as DialogPrimitive } from "radix-ui";
import { authedAssetUrl } from "@/api/client";

type PreviewImage = { url: string; original_name?: string | null };

export default function ImagePreviewDialog({
  image,
  open,
  onOpenChange,
}: {
  image: PreviewImage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-[2px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
        />
        <DialogPrimitive.Content
          aria-label={image?.original_name ?? "image preview"}
          onClick={() => onOpenChange(false)}
          className="fixed inset-0 z-50 flex items-center justify-center outline-none data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
        >
          {/* Hidden title is required by Radix for a11y; keep it for screen readers. */}
          <DialogPrimitive.Title className="sr-only">
            {image?.original_name ?? "image preview"}
          </DialogPrimitive.Title>
          {image && (
            <img
              src={authedAssetUrl(image.url)}
              alt={image.original_name ?? ""}
              className="max-h-[100vh] max-w-[100vw] cursor-zoom-out object-contain"
            />
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
