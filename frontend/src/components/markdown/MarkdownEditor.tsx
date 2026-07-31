import { useRef } from "react";
import { Textarea } from "@/components/ui/textarea";
import type { UploadedAsset } from "@/api/client";
import { cn } from "@/lib/utils";
import MarkdownEditorFrame from "./MarkdownEditorFrame";
import {
  applyMarkdownAction,
  markdownForAsset,
  type MarkdownAction,
} from "./markdown-editing";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  minHeightClassName?: string;
}

export default function MarkdownEditor({
  value,
  onChange,
  placeholder,
  minHeightClassName = "min-h-[55vh]",
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function apply(action: MarkdownAction) {
    const textarea = textareaRef.current;
    const edit = applyMarkdownAction(
      value,
      textarea?.selectionStart ?? value.length,
      textarea?.selectionEnd ?? value.length,
      action,
    );
    onChange(edit.value);
    restoreSelection(edit.selectionStart, edit.selectionEnd);
  }

  function insertAsset(asset: UploadedAsset, kind: "image" | "attachment") {
    const textarea = textareaRef.current;
    const start = textarea?.selectionStart ?? value.length;
    const end = textarea?.selectionEnd ?? start;
    const markdown = markdownForAsset(asset, kind);
    const leading = start > 0 && value[start - 1] !== "\n" ? "\n\n" : "";
    const trailing = end < value.length && value[end] !== "\n" ? "\n\n" : "";
    const next = value.slice(0, start) + leading + markdown + trailing + value.slice(end);
    onChange(next);
    const cursor = start + leading.length + markdown.length;
    restoreSelection(cursor, cursor);
  }

  function restoreSelection(start: number, end: number) {
    window.requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(start, end);
    });
  }

  return (
    <MarkdownEditorFrame onAction={apply} onInsertAsset={insertAsset}>
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        style={{ fontSize: "var(--font-ui)" }}
        className={cn(
          "rounded-none border-0 bg-transparent px-4 py-4 font-mono leading-relaxed shadow-none focus-visible:border-transparent focus-visible:ring-0",
          minHeightClassName,
        )}
      />
    </MarkdownEditorFrame>
  );
}
