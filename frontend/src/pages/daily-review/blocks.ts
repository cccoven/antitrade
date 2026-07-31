import type { ReviewBlock } from "./parser";

export type CursorAnchor = { textBlockIndex: number; cursor: number; selectionEnd?: number };

export function insertEmbedAt(
  blocks: ReviewBlock[],
  at: CursorAnchor,
  embed: Extract<ReviewBlock, { kind: "trade" | "screenshot" }>,
): ReviewBlock[] {
  const target = blocks[at.textBlockIndex];
  if (!target || target.kind !== "text") return blocks;
  const before = target.text.slice(0, at.cursor);
  const after = target.text.slice(at.cursor);
  return [
    ...blocks.slice(0, at.textBlockIndex),
    { kind: "text", text: before },
    embed,
    { kind: "text", text: after },
    ...blocks.slice(at.textBlockIndex + 1),
  ];
}

export function removeEmbedAt(blocks: ReviewBlock[], embedIndex: number): ReviewBlock[] {
  const target = blocks[embedIndex];
  if (!target || target.kind === "text") return blocks;
  const prev = blocks[embedIndex - 1];
  const next = blocks[embedIndex + 1];
  if (prev?.kind === "text" && next?.kind === "text") {
    const merged: ReviewBlock = {
      kind: "text",
      text: prev.text && next.text ? `${prev.text}\n${next.text}` : prev.text + next.text,
    };
    return [
      ...blocks.slice(0, embedIndex - 1),
      merged,
      ...blocks.slice(embedIndex + 2),
    ];
  }
  return [...blocks.slice(0, embedIndex), ...blocks.slice(embedIndex + 1)];
}

export function insertTextAt(
  blocks: ReviewBlock[],
  at: CursorAnchor,
  text: string,
): ReviewBlock[] {
  const target = blocks[at.textBlockIndex];
  if (!target || target.kind !== "text") return blocks;
  const before = target.text.slice(0, at.cursor);
  const after = target.text.slice(at.cursor);
  const merged: ReviewBlock = { kind: "text", text: `${before}${text}${after}` };
  return [
    ...blocks.slice(0, at.textBlockIndex),
    merged,
    ...blocks.slice(at.textBlockIndex + 1),
  ];
}
