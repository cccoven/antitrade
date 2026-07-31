import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Copy, Pencil } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  authedAssetUrl,
  type ChatMessage,
  type UploadedAsset,
} from "@/api/client";
import ImagePreviewDialog from "@/components/ImagePreviewDialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { assistantInputStyle, assistantToolbarStyle } from "../assistant-ui-config";
import { AgentWorkLog } from "./AgentWorkLog";
import { AssistantArtifactRenderer } from "./AssistantArtifactRenderer";

interface MessageBubbleProps {
  message: ChatMessage;
  canEdit: boolean;
  onReplace: (content: string) => void;
}

function AttachmentGrid({
  attachments,
  onPreview,
}: {
  attachments: UploadedAsset[];
  onPreview: (attachment: UploadedAsset) => void;
}) {
  if (attachments.length === 0) return null;
  return (
    <div
      className={attachments.length === 1
        ? "w-72 max-w-full"
        : "grid w-80 max-w-full grid-cols-2 gap-1.5"}
    >
      {attachments.map((attachment) => (
        <button
          key={attachment.id}
          type="button"
          className="aspect-video overflow-hidden rounded-lg border border-border bg-muted"
          onClick={() => onPreview(attachment)}
        >
          <img
            src={authedAssetUrl(attachment.url)}
            alt={attachment.original_name ?? ""}
            className="h-full w-full object-cover transition-transform hover:scale-[1.02]"
          />
        </button>
      ))}
    </div>
  );
}

function formatMessageTime(createdAt: string, language: string): string {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(language, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function MessageBubble({ message, canEdit, onReplace }: MessageBubbleProps) {
  const { t, i18n } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState<UploadedAsset | null>(null);
  const isUser = message.role === "user";
  const time = formatMessageTime(message.created_at, i18n.resolvedLanguage || i18n.language);

  const copyMessage = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const startEditing = () => {
    setEditValue(message.content);
    setIsEditing(true);
  };

  const submitEdit = () => {
    const content = editValue.trim();
    if (!content || content === message.content) return;
    setIsEditing(false);
    onReplace(content);
  };

  if (isEditing && isUser) {
    return (
      <>
        <div className="flex justify-end">
          <div className="flex w-full max-w-[85%] flex-col items-end gap-1.5">
            <AttachmentGrid
              attachments={message.attachments ?? []}
              onPreview={setPreview}
            />
            <div className="w-full rounded-xl bg-primary p-3 text-primary-foreground">
              <Textarea
                autoFocus
                value={editValue}
                onChange={(event) => setEditValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") setIsEditing(false);
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) submitEdit();
                }}
                className="min-h-20 resize-none border-0 bg-transparent p-0 text-ui text-primary-foreground shadow-none focus-visible:border-transparent focus-visible:ring-0"
                style={assistantInputStyle}
              />
              <div className="mt-3 flex justify-end gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  style={assistantToolbarStyle}
                  onClick={() => setIsEditing(false)}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  size="sm"
                  className="bg-foreground text-background hover:bg-foreground/90"
                  style={assistantToolbarStyle}
                  disabled={!editValue.trim() || editValue.trim() === message.content}
                  onClick={submitEdit}
                >
                  {t("assistant.send")}
                </Button>
              </div>
            </div>
          </div>
        </div>
        <ImagePreviewDialog
          image={preview}
          open={preview !== null}
          onOpenChange={(open) => !open && setPreview(null)}
        />
      </>
    );
  }

  if (!isUser) {
    return (
      <div className="group w-full">
        {message.work && <AgentWorkLog work={message.work} />}
        {message.artifacts?.length ? <AssistantArtifactRenderer artifacts={message.artifacts} /> : null}
        {(message.content || !message.work) && (
          <div className="markdown w-full text-ui [&>*:last-child]:mb-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || "…"}
            </ReactMarkdown>
          </div>
        )}
        {message.content && (
          <div className="pointer-events-none mt-1 flex h-6 items-center text-muted-foreground opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
            <Button
              variant="ghost"
              size="icon-xs"
              className="size-6 rounded-md"
              style={assistantToolbarStyle}
              aria-label={t(copied ? "assistant.message.copied" : "assistant.message.copy")}
              title={t(copied ? "assistant.message.copied" : "assistant.message.copy")}
              onClick={() => void copyMessage()}
            >
              {copied ? (
                <Check className="size-[var(--icon-xs)]" />
              ) : (
                <Copy className="size-[var(--icon-xs)]" />
              )}
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      <div className="group flex justify-end">
        <div className="flex max-w-[85%] flex-col items-end gap-1.5">
          <AttachmentGrid
            attachments={message.attachments ?? []}
            onPreview={setPreview}
          />
          {message.content && (
            <div className="rounded-lg bg-primary px-3 py-2 text-ui text-primary-foreground">
              <span className="whitespace-pre-wrap">{message.content}</span>
            </div>
          )}
          <div className="pointer-events-none flex h-6 items-center gap-0.5 px-1 text-micro text-muted-foreground opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
            {time && <span className="mr-0.5 tabular-nums">{time}</span>}
            <Button
              variant="ghost"
              size="icon-xs"
              className="size-6 rounded-md"
              style={assistantToolbarStyle}
              aria-label={t(copied ? "assistant.message.copied" : "assistant.message.copy")}
              title={t(copied ? "assistant.message.copied" : "assistant.message.copy")}
              onClick={() => void copyMessage()}
            >
              {copied ? (
                <Check className="size-[var(--icon-xs)]" />
              ) : (
                <Copy className="size-[var(--icon-xs)]" />
              )}
            </Button>
            {canEdit && (
              <Button
                variant="ghost"
                size="icon-xs"
                className="size-6 rounded-md"
                style={assistantToolbarStyle}
                aria-label={t("assistant.message.edit")}
                title={t("assistant.message.edit")}
                onClick={startEditing}
              >
                <Pencil className="size-[var(--icon-xs)]" />
              </Button>
            )}
          </div>
        </div>
      </div>
      <ImagePreviewDialog
        image={preview}
        open={preview !== null}
        onOpenChange={(open) => !open && setPreview(null)}
      />
    </>
  );
}
