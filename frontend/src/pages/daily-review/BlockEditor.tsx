import { useCallback, useImperativeHandle, useRef, forwardRef } from "react";
import { useTranslation } from "react-i18next";
import type { UploadedAsset } from "@/api/client";
import MarkdownEditorFrame from "@/components/markdown/MarkdownEditorFrame";
import {
  applyMarkdownAction,
  markdownForAsset,
  type MarkdownAction,
} from "@/components/markdown/markdown-editing";
import { Textarea } from "@/components/ui/textarea";
import { dailyReviewControlStyle } from "@/pages/daily-review-ui-config";
import type { Trade, TradeImage } from "@/api/client";
import type { ReviewBlock } from "./parser";
import ReviewBody from "./ReviewBody";
import type { CursorAnchor } from "./blocks";

export interface BlockEditorHandle {
  getActiveAnchor(): CursorAnchor | null;
}

export interface BlockEditorProps {
  blocks: ReviewBlock[];
  onChange: (blocks: ReviewBlock[]) => void;
  trades: Trade[];
  onPreviewImage: (image: TradeImage) => void;
  onRemoveEmbed: (index: number) => void;
}

const BlockEditor = forwardRef<BlockEditorHandle, BlockEditorProps>(function BlockEditor(
  { blocks, onChange, trades, onPreviewImage, onRemoveEmbed },
  ref,
) {
  const { t } = useTranslation();
  const activeAnchorRef = useRef<CursorAnchor | null>(null);
  const textareaRefs = useRef<Map<number, HTMLTextAreaElement>>(new Map());

  useImperativeHandle(
    ref,
    () => ({
      getActiveAnchor: () => activeAnchorRef.current,
    }),
    [],
  );

  const updateText = useCallback(
    (index: number, next: string) => {
      const updated = blocks.map((b, i) =>
        i === index && b.kind === "text" ? { ...b, text: next } : b,
      );
      onChange(updated);
    },
    [blocks, onChange],
  );

  const activeAnchor = useCallback((): CursorAnchor | null => {
    if (activeAnchorRef.current) return activeAnchorRef.current;
    const textBlockIndex = blocks.findIndex((block) => block.kind === "text");
    return textBlockIndex >= 0 ? { textBlockIndex, cursor: 0, selectionEnd: 0 } : null;
  }, [blocks]);

  const restoreSelection = (index: number, start: number, end: number) => {
    window.requestAnimationFrame(() => {
      const textarea = textareaRefs.current.get(index);
      textarea?.focus();
      textarea?.setSelectionRange(start, end);
      activeAnchorRef.current = { textBlockIndex: index, cursor: start, selectionEnd: end };
    });
  };

  const applyAction = (action: MarkdownAction) => {
    const anchor = activeAnchor();
    if (!anchor) return;
    const target = blocks[anchor.textBlockIndex];
    if (!target || target.kind !== "text") return;
    const edit = applyMarkdownAction(
      target.text,
      anchor.cursor,
      anchor.selectionEnd ?? anchor.cursor,
      action,
    );
    updateText(anchor.textBlockIndex, edit.value);
    restoreSelection(anchor.textBlockIndex, edit.selectionStart, edit.selectionEnd);
  };

  const insertAsset = (asset: UploadedAsset, kind: "image" | "attachment") => {
    const anchor = activeAnchor();
    if (!anchor) return;
    const target = blocks[anchor.textBlockIndex];
    if (!target || target.kind !== "text") return;
    const end = anchor.selectionEnd ?? anchor.cursor;
    const markdown = markdownForAsset(asset, kind);
    const leading = anchor.cursor > 0 && target.text[anchor.cursor - 1] !== "\n" ? "\n\n" : "";
    const trailing = end < target.text.length && target.text[end] !== "\n" ? "\n\n" : "";
    const next = target.text.slice(0, anchor.cursor) + leading + markdown + trailing + target.text.slice(end);
    updateText(anchor.textBlockIndex, next);
    const cursor = anchor.cursor + leading.length + markdown.length;
    restoreSelection(anchor.textBlockIndex, cursor, cursor);
  };

  const handleFocus = (index: number, ta: HTMLTextAreaElement) => {
    activeAnchorRef.current = {
      textBlockIndex: index,
      cursor: ta.selectionStart ?? ta.value.length,
      selectionEnd: ta.selectionEnd ?? ta.value.length,
    };
  };

  const handleSelect = (index: number, ta: HTMLTextAreaElement) => {
    activeAnchorRef.current = {
      textBlockIndex: index,
      cursor: ta.selectionStart ?? ta.value.length,
      selectionEnd: ta.selectionEnd ?? ta.value.length,
    };
  };

  return (
    <MarkdownEditorFrame onAction={applyAction} onInsertAsset={insertAsset}>
      <div className="flex min-h-[420px] flex-col gap-2 p-3">
        <ReviewBody
          blocks={blocks}
          mode="edit"
          trades={trades}
          onPreviewImage={onPreviewImage}
          onRemoveEmbed={onRemoveEmbed}
          renderTextBlock={(block, i) => (
            <Textarea
              ref={(el) => {
                if (el) textareaRefs.current.set(i, el);
                else textareaRefs.current.delete(i);
              }}
              value={block.text}
              onChange={(e) => updateText(i, e.target.value)}
              onFocus={(e) => handleFocus(i, e.currentTarget)}
              onSelect={(e) => handleSelect(i, e.currentTarget)}
              rows={Math.max(4, Math.min(24, block.text.split("\n").length + 2))}
              style={dailyReviewControlStyle}
              className="resize-y rounded-lg border-border/70 bg-background/50 font-mono leading-relaxed shadow-none"
              placeholder={t("dailyReview.bodyPlaceholder")}
            />
          )}
        />
      </div>
    </MarkdownEditorFrame>
  );
});

export default BlockEditor;
