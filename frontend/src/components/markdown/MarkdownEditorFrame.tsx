import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Bold,
  Code2,
  Heading2,
  ImagePlus,
  Italic,
  Link2,
  List,
  ListOrdered,
  Loader2,
  Paperclip,
  Quote,
} from "lucide-react";
import { uploadAsset, type UploadedAsset } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { MarkdownAction } from "./markdown-editing";

const controlStyle = { fontSize: "var(--font-ui)", fontWeight: 400 } as const;
const attachmentAccept = [
  "image/png", "image/jpeg", "image/webp", "application/pdf", "text/plain",
  "text/markdown", "text/csv", "application/json", "application/zip",
  ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
].join(",");

interface Props {
  children: ReactNode;
  onAction: (action: MarkdownAction) => void;
  onInsertAsset: (asset: UploadedAsset, kind: "image" | "attachment") => void;
  className?: string;
}

export default function MarkdownEditorFrame({
  children,
  onAction,
  onInsertAsset,
  className,
}: Props) {
  const { t } = useTranslation();
  const imageInputRef = useRef<HTMLInputElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  async function uploadFiles(files: File[]) {
    if (files.length === 0) return;
    setUploading(true);
    try {
      for (const file of files) {
        const asset = await uploadAsset(file);
        onInsertAsset(asset, file.type.startsWith("image/") ? "image" : "attachment");
      }
    } finally {
      setUploading(false);
      if (imageInputRef.current) imageInputRef.current.value = "";
      if (attachmentInputRef.current) attachmentInputRef.current.value = "";
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void uploadFiles(Array.from(event.dataTransfer.files));
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-card/40 shadow-sm transition-colors focus-within:border-ring",
        dragging && "border-primary bg-primary/5",
        className,
      )}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
      }}
      onDrop={handleDrop}
    >
      <div className="flex min-h-10 flex-wrap items-center gap-0.5 border-b border-border bg-muted/30 px-2 py-1">
        <ToolbarButton label={t("markdown.bold")} onClick={() => onAction("bold")}><Bold /></ToolbarButton>
        <ToolbarButton label={t("markdown.italic")} onClick={() => onAction("italic")}><Italic /></ToolbarButton>
        <ToolbarButton label={t("markdown.heading")} onClick={() => onAction("heading")}><Heading2 /></ToolbarButton>
        <Separator orientation="vertical" className="mx-1 h-5" />
        <ToolbarButton label={t("markdown.bulletList")} onClick={() => onAction("bulletList")}><List /></ToolbarButton>
        <ToolbarButton label={t("markdown.numberedList")} onClick={() => onAction("numberedList")}><ListOrdered /></ToolbarButton>
        <ToolbarButton label={t("markdown.quote")} onClick={() => onAction("quote")}><Quote /></ToolbarButton>
        <ToolbarButton label={t("markdown.code")} onClick={() => onAction("code")}><Code2 /></ToolbarButton>
        <ToolbarButton label={t("markdown.link")} onClick={() => onAction("link")}><Link2 /></ToolbarButton>
        <Separator orientation="vertical" className="mx-1 h-5" />
        <ToolbarButton
          label={t("markdown.image")}
          onClick={() => imageInputRef.current?.click()}
          disabled={uploading}
        >
          <ImagePlus />
        </ToolbarButton>
        <ToolbarButton
          label={t("markdown.attachment")}
          onClick={() => attachmentInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? <Loader2 className="animate-spin" /> : <Paperclip />}
        </ToolbarButton>
        <input
          ref={imageInputRef}
          className="hidden"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          onChange={(event) => void uploadFiles(Array.from(event.target.files ?? []))}
        />
        <input
          ref={attachmentInputRef}
          className="hidden"
          type="file"
          accept={attachmentAccept}
          multiple
          onChange={(event) => void uploadFiles(Array.from(event.target.files ?? []))}
        />
      </div>

      {children}

      <div className="flex items-center justify-end gap-3 border-t border-border bg-muted/20 px-3 py-1.5 text-micro text-muted-foreground">
        <span className="hidden sm:inline">{t("markdown.dropHint")}</span>
      </div>

      {dragging && (
        <div className="pointer-events-none absolute inset-2 z-10 flex items-center justify-center rounded-lg border border-dashed border-primary bg-background/90 text-ui font-medium text-primary">
          {t("markdown.dropHere")}
        </div>
      )}
    </div>
  );
}

function ToolbarButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          style={controlStyle}
          onClick={onClick}
          disabled={disabled}
          aria-label={label}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
