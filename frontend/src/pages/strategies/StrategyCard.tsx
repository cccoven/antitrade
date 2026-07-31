import { useState } from "react";
import { FileText, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import type { Strategy } from "@/api/strategies";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { btnStyle, strategiesCardDensity } from "../strategies-ui-config";
import { derivePreview } from "./strategy-preview";

interface Props {
  strategy: Strategy;
  onClick: () => void;
  onDelete: () => void;
}

export default function StrategyCard({ strategy, onClick, onDelete }: Props) {
  const { t } = useTranslation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const preview = derivePreview(strategy.body);
  const tagsToShow = strategy.tags.slice(0, 2);
  const overflow = strategy.tags.length - tagsToShow.length;
  const density = strategiesCardDensity;

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick();
          }
        }}
        className={cn(
          "group relative flex cursor-pointer flex-col overflow-hidden rounded-md border border-border bg-card text-left transition-colors",
          "hover:border-primary/40",
        )}
      >
        <Button
          variant="ghost"
          size="icon-sm"
          style={btnStyle}
          className="absolute right-2 top-2 z-10 bg-card/80 opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            setConfirmOpen(true);
          }}
          aria-label={t("strategies.delete")}
        >
          <Trash2 className="size-[var(--icon-sm)] text-destructive" />
        </Button>

        {preview.kind === "image" && (
          <div
            className={cn(
              density.previewAspectClassName,
              "w-full overflow-hidden bg-muted/40",
            )}
          >
            <img src={preview.url} alt="" className="h-full w-full object-cover" />
          </div>
        )}
        <div
          className={cn(
            "flex flex-col",
            preview.kind === "image" && "border-t border-border",
            density.bodyClassName,
          )}
        >
          <div className={cn("flex items-center text-foreground", density.titleClassName)}>
            <FileText className="mt-0.5 size-[var(--icon-sm)] shrink-0 text-muted-foreground" />
            <span className="line-clamp-2">{strategy.title || "Untitled"}</span>
          </div>
          {tagsToShow.length > 0 && (
            <div className={cn("flex flex-wrap text-caption text-muted-foreground", density.tagListClassName)}>
              {tagsToShow.map((tag) => (
                <span key={tag} className={density.tagClassName}>{tag}</span>
              ))}
              {overflow > 0 && <span className="px-0.5 py-0.5">+{overflow}</span>}
            </div>
          )}
          <div
            className={cn(
              "flex items-center justify-between gap-3 text-caption text-muted-foreground",
              density.footerClassName,
            )}
          >
            <span
              className="tabular-nums"
              title={t("strategies.winRateSample", { count: strategy.trade_count })}
            >
              {t("strategies.winRate")}{" "}
              <span className="text-foreground">
                {strategy.win_rate === null ? "—" : `${strategy.win_rate.toFixed(1)}%`}
              </span>
            </span>
            <div className="flex shrink-0 items-center">
              <RelativeTime iso={strategy.updated_at} />
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("strategies.deleteConfirmTitle")}
        description={t("strategies.deleteConfirmBody")}
        onConfirm={onDelete}
        confirmLabel={t("strategies.delete")}
        cancelLabel={t("common.cancel")}
      />
    </>
  );
}

function RelativeTime({ iso }: { iso: string }) {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const day = 86_400_000;
  if (diff < day) return <span>today</span>;
  if (diff < 7 * day) return <span>{Math.floor(diff / day)}d ago</span>;
  if (diff < 30 * day) return <span>{Math.floor(diff / (7 * day))}w ago</span>;
  return <span>{Math.floor(diff / (30 * day))}mo ago</span>;
}
