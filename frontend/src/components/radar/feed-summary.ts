/** Feed summaries arrive as HTML. Extract paragraphs (preserving breaks) + image srcs. */
export function parseSummary(html: string): {
  text: string;
  paragraphs: string[];
  images: string[];
} {
  if (typeof window === "undefined" || !("DOMParser" in window)) {
    const flat = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
    return { text: flat, paragraphs: flat ? [flat] : [], images: [] };
  }
  const doc = new DOMParser().parseFromString(html, "text/html");
  const images = Array.from(doc.querySelectorAll("img"))
    .map((img) => img.getAttribute("src") || "")
    .filter((src) => /^https?:\/\//.test(src));

  // Prefer block-level elements as paragraph boundaries; fall back to <br>/newlines.
  let paragraphs = Array.from(doc.querySelectorAll("p, li, div"))
    .map((el) => (el.textContent ?? "").replace(/\s+/g, " ").trim())
    .filter(Boolean);
  if (paragraphs.length === 0) {
    paragraphs = (doc.body.textContent ?? "")
      .split(/\n{2,}|\r\n/)
      .map((s) => s.replace(/\s+/g, " ").trim())
      .filter(Boolean);
  }
  const text = paragraphs.join("\n\n");
  return { text, paragraphs, images };
}

/** Strip HTML tags/entities from a short string (e.g. a title that arrives as HTML). */
export function stripHtml(input: string | null | undefined): string {
  if (!input) return "";
  if (typeof window === "undefined" || !("DOMParser" in window)) {
    return input.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  }
  const doc = new DOMParser().parseFromString(input, "text/html");
  return (doc.body.textContent ?? "").replace(/\s+/g, " ").trim();
}

/** True when the url is a real, openable web link (some feeds store opaque ids). */
export function isWebUrl(url: string | null | undefined): boolean {
  return typeof url === "string" && /^https?:\/\//.test(url);
}

/**
 * Resolve a feed item's stored url to a real, openable web link.
 * Most sources store the canonical article url directly. jin10 stores an
 * opaque id (`jin10:index:<flashId>`) that maps to the flash detail page.
 * Returns null when no web url can be derived.
 */
export function resolveFeedUrl(url: string | null | undefined): string | null {
  if (isWebUrl(url)) return url as string;
  if (typeof url === "string") {
    const m = url.match(/^jin10:\w+:(\d+)$/);
    if (m) return `https://flash.jin10.com/detail/${m[1]}`;
  }
  return null;
}
