import type { UploadedAsset } from "@/api/client";

export type MarkdownAction =
  | "bold"
  | "italic"
  | "heading"
  | "bulletList"
  | "numberedList"
  | "quote"
  | "code"
  | "link";

export interface MarkdownEdit {
  value: string;
  selectionStart: number;
  selectionEnd: number;
}

export function applyMarkdownAction(
  value: string,
  selectionStart: number,
  selectionEnd: number,
  action: MarkdownAction,
): MarkdownEdit {
  const start = Math.max(0, Math.min(selectionStart, value.length));
  const end = Math.max(start, Math.min(selectionEnd, value.length));
  const selected = value.slice(start, end);

  if (action === "bold") return wrap(value, start, end, selected || "bold", "**", "**");
  if (action === "italic") return wrap(value, start, end, selected || "italic", "_", "_");
  if (action === "code") return wrap(value, start, end, selected || "code", "`", "`");
  if (action === "link") {
    const label = selected || "link text";
    return replace(value, start, end, `[${label}](https://)`, start + label.length + 3, start + label.length + 11);
  }

  const lineStart = value.lastIndexOf("\n", start - 1) + 1;
  const nextBreak = value.indexOf("\n", end);
  const lineEnd = nextBreak === -1 ? value.length : nextBreak;
  const block = value.slice(lineStart, lineEnd);
  const prefix = action === "heading" ? "## " : action === "quote" ? "> " : action === "bulletList" ? "- " : "1. ";
  const replacement = block
    .split("\n")
    .map((line, index) => {
      if (action === "numberedList") return `${index + 1}. ${line}`;
      return `${prefix}${line}`;
    })
    .join("\n");
  return replace(value, lineStart, lineEnd, replacement, lineStart, lineStart + replacement.length);
}

export function markdownForAsset(asset: UploadedAsset, kind: "image" | "attachment"): string {
  const name = escapeLabel(asset.original_name || (kind === "image" ? "image" : "attachment"));
  return kind === "image" ? `![${name}](${asset.url})` : `[${name}](${asset.url})`;
}

function wrap(
  value: string,
  start: number,
  end: number,
  content: string,
  before: string,
  after: string,
): MarkdownEdit {
  const replacement = `${before}${content}${after}`;
  const selectionStart = start + before.length;
  return replace(value, start, end, replacement, selectionStart, selectionStart + content.length);
}

function replace(
  value: string,
  start: number,
  end: number,
  replacement: string,
  selectionStart: number,
  selectionEnd: number,
): MarkdownEdit {
  return {
    value: value.slice(0, start) + replacement + value.slice(end),
    selectionStart,
    selectionEnd,
  };
}

function escapeLabel(value: string): string {
  return value.replace(/[\[\]]/g, "");
}
