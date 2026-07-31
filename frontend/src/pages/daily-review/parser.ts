export type ReviewBlock =
  | { kind: "text"; text: string }
  | { kind: "trade"; id: string }
  | { kind: "screenshot"; id: string };

const TRADE_RE = /^::trade id="([^"]+)"::$/;
const SCREENSHOT_RE = /^::screenshot id="([^"]+)"::$/;

export function parseReviewBody(body: string): ReviewBlock[] {
  const lines = body.split("\n");
  const blocks: ReviewBlock[] = [];
  let buf: string[] = [];

  const flushText = () => {
    blocks.push({ kind: "text", text: buf.join("\n") });
    buf = [];
  };

  for (const line of lines) {
    const tradeMatch = TRADE_RE.exec(line);
    const screenshotMatch = SCREENSHOT_RE.exec(line);
    if (tradeMatch) {
      flushText();
      blocks.push({ kind: "trade", id: tradeMatch[1] });
    } else if (screenshotMatch) {
      flushText();
      blocks.push({ kind: "screenshot", id: screenshotMatch[1] });
    } else {
      buf.push(line);
    }
  }
  flushText();

  // Invariant: text blocks bookend every embed
  const normalized: ReviewBlock[] = [];
  let lastWasText = false;
  for (const b of blocks) {
    if (b.kind === "text") {
      if (lastWasText) {
        const prev = normalized[normalized.length - 1] as { kind: "text"; text: string };
        prev.text = prev.text + "\n" + b.text;
      } else {
        normalized.push(b);
        lastWasText = true;
      }
    } else {
      if (!lastWasText) normalized.push({ kind: "text", text: "" });
      normalized.push(b);
      lastWasText = false;
    }
  }
  if (!lastWasText) normalized.push({ kind: "text", text: "" });
  return normalized;
}

export function serializeReviewBlocks(blocks: ReviewBlock[]): string {
  const lines: string[] = [];
  blocks.forEach((b, i) => {
    if (b.kind === "text") {
      // Skip empty text blocks that were injected as bookends around embeds
      const prevIsEmbed = i > 0 && blocks[i - 1].kind !== "text";
      const nextIsEmbed = i < blocks.length - 1 && blocks[i + 1].kind !== "text";
      if (b.text === "" && (prevIsEmbed || nextIsEmbed)) {
        return;
      }
      lines.push(b.text);
    } else if (b.kind === "trade") {
      lines.push(`::trade id="${b.id}"::`);
    } else {
      lines.push(`::screenshot id="${b.id}"::`);
    }
  });
  return lines.join("\n");
}
