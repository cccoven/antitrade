import { authedAssetUrl } from "@/api/client";

export type StrategyPreview =
  | { kind: "image"; url: string }
  | { kind: "text"; excerpt: string }
  | { kind: "empty" };

const IMAGE_RE = /!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/;

export function derivePreview(body: string): StrategyPreview {
  if (!body) return { kind: "empty" };

  const img = body.match(IMAGE_RE);
  if (img && img[1]) {
    const raw = img[1].trim();
    const url = raw.startsWith("/api/uploads/") ? authedAssetUrl(raw) : raw;
    return { kind: "image", url };
  }

  const stripped = body
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/`{1,3}[^`]*`{1,3}/g, "")
    .replace(/\!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .trim();

  if (!stripped) return { kind: "empty" };
  const excerpt = stripped.length > 200 ? stripped.slice(0, 200) + "…" : stripped;
  return { kind: "text", excerpt };
}
