import { cn } from "@/lib/utils";
import { authedAssetUrl, type Trade, type TradeImage } from "@/api/client";
import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";
import { useJournalSettings } from "@/journal/journal-settings-context";
import type { ReviewBlock } from "./parser";

type Mode = "edit" | "read" | "share";

export interface ReviewBodyProps {
  blocks: ReviewBlock[];
  mode: Mode;
  trades: Trade[];
  onRemoveEmbed?: (embedIndex: number) => void;
  onPreviewImage?: (image: TradeImage) => void;
  renderTextBlock?: (block: { text: string }, index: number) => React.ReactNode;
}

export default function ReviewBody({
  blocks,
  mode,
  trades,
  onRemoveEmbed,
  onPreviewImage,
  renderTextBlock,
}: ReviewBodyProps) {
  const tradeById = new Map(trades.map((t) => [t.id, t]));
  const imageById = new Map<string, { trade: Trade; image: TradeImage }>();
  trades.forEach((t) =>
    t.images?.forEach((img) => imageById.set(img.id, { trade: t, image: img })),
  );

  return (
    <div className="flex flex-col gap-2">
      {blocks.map((block, i) => {
        if (block.kind === "text") {
          if (renderTextBlock) return <div key={i}>{renderTextBlock(block, i)}</div>;
          return (
            <RenderedMarkdown key={i} text={block.text} mode={mode} />
          );
        }
        if (block.kind === "trade") {
          const trade = tradeById.get(block.id);
          return (
            <TradeEmbed
              key={i}
              index={i}
              trade={trade ?? null}
              mode={mode}
              onRemove={onRemoveEmbed}
            />
          );
        }
        const ref = imageById.get(block.id);
        return (
          <ScreenshotEmbed
            key={i}
            index={i}
            trade={ref?.trade ?? null}
            image={ref?.image ?? null}
            mode={mode}
            onPreview={onPreviewImage}
            onRemove={onRemoveEmbed}
          />
        );
      })}
    </div>
  );
}

function RenderedMarkdown({ text, mode }: { text: string; mode: Mode }) {
  return <MarkdownRenderer text={text} className={cn(mode === "share" && "leading-loose")} />;
}

function TradeEmbed({
  trade,
  mode,
  index,
  onRemove,
}: {
  trade: Trade | null;
  mode: Mode;
  index: number;
  onRemove?: (i: number) => void;
}) {
  const { displayMoney } = useJournalSettings();
  if (!trade) {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-caption text-muted-foreground">
        内容已删除
      </div>
    );
  }
  const compact = mode === "share";
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-md border bg-[var(--chip-bg)] p-3",
        compact ? "border-border/60 px-2 py-1" : "border-primary/40",
      )}
    >
      <div className="min-w-0">
        <div className="text-caption uppercase tracking-wide text-primary">▣ trade</div>
        <div className="truncate text-ui font-medium text-foreground">
          {trade.symbol} · {trade.direction}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "text-ui font-semibold",
            trade.pnl != null && trade.pnl < 0
              ? "text-destructive"
              : "text-[var(--success)]",
          )}
        >
          {displayMoney(trade.pnl, { signed: true })}
        </span>
        {mode === "edit" && onRemove && (
          <button
            type="button"
            className="text-caption text-muted-foreground hover:text-foreground"
            onClick={() => onRemove(index)}
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

function ScreenshotEmbed({
  trade,
  image,
  mode,
  index,
  onPreview,
  onRemove,
}: {
  trade: Trade | null;
  image: TradeImage | null;
  mode: Mode;
  index: number;
  onPreview?: (image: TradeImage) => void;
  onRemove?: (i: number) => void;
}) {
  if (!image) {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-caption text-muted-foreground">
        内容已删除
      </div>
    );
  }
  return (
    <figure className="flex items-center gap-3 rounded-md border border-border bg-muted/30 p-2">
      <button
        type="button"
        className="overflow-hidden rounded border border-border bg-background"
        onClick={() => onPreview?.(image)}
      >
        <img
          src={authedAssetUrl(image.url)}
          alt={image.original_name || trade?.symbol || ""}
          className="h-16 w-28 object-cover"
        />
      </button>
      <figcaption className="flex-1 text-caption text-muted-foreground">
        {image.original_name || trade?.symbol || "screenshot"}
      </figcaption>
      {mode === "edit" && onRemove && (
        <button
          type="button"
          className="text-caption text-muted-foreground hover:text-foreground"
          onClick={() => onRemove(index)}
        >
          ✕
        </button>
      )}
    </figure>
  );
}
