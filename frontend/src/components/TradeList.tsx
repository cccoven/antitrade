import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";
import { format } from "date-fns";
import { Pencil, Trash2, ChevronDown, Play, Images } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import ImageAnnotationDialog from "@/components/ImageAnnotationDialog";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { journalTableControlSizes } from "@/pages/journal-ui-config";
import { cn } from "@/lib/utils";
import { authedAssetUrl, type Trade, type TradeImage } from "@/api/client";
import type { UseSelectionApi } from "@/hooks/useSelection";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface TradeListProps {
  trades: Trade[];
  onEdit: (trade: Trade) => void;
  onDelete: (tradeId: string) => void;
  selection?: UseSelectionApi;
}

function formatValue(value: number | null): string {
  if (value == null) return "\u2014";
  return String(value);
}

function formatTime(iso: string | null): string {
  if (!iso) return "\u2014";
  try {
    return format(new Date(iso), "MM/dd HH:mm");
  } catch {
    return "\u2014";
  }
}

interface DenseMetricProps {
  label: string;
  value: string;
  valueClassName?: string;
}

function DenseMetric({
  label,
  value,
  valueClassName,
}: DenseMetricProps) {
  return (
    <div className="grid gap-0.5">
      <span className="text-caption text-muted-foreground">{label}</span>
      <span className={cn("text-ui font-medium text-foreground", valueClassName)}>
        {value}
      </span>
    </div>
  );
}

export default function TradeList({
  trades,
  onEdit,
  onDelete,
  selection,
}: TradeListProps) {
  const { t } = useTranslation();
  const { currencyCode, displayMoney } = useJournalSettings();
  const navigate = useNavigate();
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [previewImage, setPreviewImage] = useState<TradeImage | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (!trades || trades.length === 0) {
    return (
      <Empty className="min-h-[220px] border border-dashed border-border bg-[var(--chip-bg)] p-8">
        <EmptyHeader>
          <EmptyTitle className="text-subheading text-foreground">
            {t("journal.noTrades")}
          </EmptyTitle>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <>
    <Table className="min-w-[860px] table-fixed">
      <colgroup>
        {selection && <col className="w-[5%]" />}
        <col className={selection ? "w-[17%]" : "w-[18%]"} />
        <col className={selection ? "w-[11%]" : "w-[12%]"} />
        <col className={selection ? "w-[23%]" : "w-[24%]"} />
        <col className={selection ? "w-[13%]" : "w-[14%]"} />
        <col className={selection ? "w-[21%]" : "w-[22%]"} />
        <col className="w-[10%]" />
      </colgroup>
      <TableHeader className="[&_tr]:border-b-0">
        <TableRow>
          {selection && (() => {
            const pageIds = trades.map((tr) => tr.id);
            const onPageCount = pageIds.filter((id) => selection.selectedIds.has(id)).length;
            const headerChecked: boolean | "indeterminate" =
              selection.allMatching || (onPageCount === pageIds.length && pageIds.length > 0)
                ? true
                : onPageCount === 0
                  ? false
                  : "indeterminate";
            return (
              <TableHead className="h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 first:rounded-l-[10px]">
                <Checkbox
                  checked={headerChecked}
                  onCheckedChange={() => selection.toggleAllOnPage(pageIds)}
                  aria-label="toggle all on page"
                />
              </TableHead>
            );
          })()}
          <TableHead className={`h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-caption font-medium tracking-[0.03em] text-muted-foreground${selection ? "" : " first:rounded-l-[10px]"}`}>
            {t("journal.symbol")}
          </TableHead>
          <TableHead className="h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-caption font-medium tracking-[0.03em] text-muted-foreground">
            {t("journal.direction")}
          </TableHead>
          <TableHead className="h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-caption font-medium tracking-[0.03em] text-muted-foreground">
            {t("journal.openPrice")} / {t("journal.closePrice")}
          </TableHead>
          <TableHead className="h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-right text-caption font-medium tracking-[0.03em] text-muted-foreground">
            {t("journal.pnl")}{currencyCode ? ` (${currencyCode})` : ""}
          </TableHead>
          <TableHead className="h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-caption font-medium tracking-[0.03em] text-muted-foreground">
            {t("journal.openTime")} / {t("journal.closeTime")}
          </TableHead>
          <TableHead className="h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-right text-caption font-medium tracking-[0.03em] text-muted-foreground last:rounded-r-[10px]">
            {t("journal.actions")}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {trades.map((trade) => {
          const expanded = expandedIds.has(trade.id);
          const pnlVal = trade.pnl;
          const hasImages = (trade.images?.length ?? 0) > 0;
          const hasDetails = trade.tags.length > 0 || trade.notes || hasImages
            || Boolean(trade.setup_type || trade.emotional_state || trade.mistakes.length)
            || trade.confidence != null || trade.execution_quality != null
            || trade.compliance.results.length > 0;

          return (
            <Fragment key={trade.id}>
              <TableRow
                onClick={() => hasDetails && toggleExpand(trade.id)}
                role={hasDetails ? "button" : undefined}
                tabIndex={hasDetails ? 0 : undefined}
                onKeyDown={
                  hasDetails
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          toggleExpand(trade.id);
                        }
                      }
                    : undefined
                }
                className={cn(
                  hasDetails && "cursor-pointer",
                  expanded && "border-b-0",
                  "border-b border-border/60"
                )}
              >
                {selection && (
                  <TableCell
                    className="px-3 py-3"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={selection.isSelected(trade.id)}
                      onCheckedChange={() => selection.toggle(trade.id)}
                      onClick={(e) => {
                        if ((e as React.MouseEvent).shiftKey) {
                          e.preventDefault();
                          selection.shiftSelect(trade.id, trades.map((tr) => tr.id));
                        }
                      }}
                      aria-label={`select ${trade.symbol}`}
                    />
                  </TableCell>
                )}
                <TableCell className="px-3 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-ui font-semibold text-foreground">
                      {trade.symbol}
                    </span>
                    <Badge
                      variant="outline"
                      className={cn(
                        "shrink-0 rounded-md px-1.5 py-0 text-micro",
                        trade.position_status === "open"
                          ? "border-[color-mix(in_srgb,var(--warning)_30%,transparent)] text-[var(--warning)]"
                          : "text-muted-foreground",
                      )}
                    >
                      {t(`journal.status.${trade.position_status}`)}
                    </Badge>
                    {hasImages && (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-[var(--accent-soft)] px-1.5 py-0.5 text-micro text-muted-foreground">
                        <Images className="size-[var(--icon-xs)]" />
                        {trade.images.length}
                      </span>
                    )}
                    {hasDetails && (
                      <ChevronDown
                        className={cn(
                          "size-[var(--icon-xs)] shrink-0 text-muted-foreground transition-transform duration-150",
                          expanded && "rotate-180"
                        )}
                      />
                    )}
                  </div>
                </TableCell>
                <TableCell className="px-3 py-3">
                  <Badge
                    variant="ghost"
                    className={cn(
                      "rounded-md border border-transparent px-2 py-0.5",
                      journalTableControlSizes.directionBadgeText,
                      trade.direction === "long"
                        ? "bg-[color-mix(in_srgb,var(--success)_12%,transparent)] text-[var(--success)]"
                        : "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)] text-[var(--danger)]"
                    )}
                  >
                    {t(trade.direction === "long" ? "journal.long" : "journal.short")}
                  </Badge>
                </TableCell>
                <TableCell className="whitespace-normal px-3 py-3">
                  <div className="grid grid-cols-2 gap-3">
                    <DenseMetric
                      label={t("journal.openPrice")}
                      value={formatValue(trade.open_price)}
                    />
                    <DenseMetric
                      label={t("journal.closePrice")}
                      value={formatValue(trade.close_price)}
                    />
                  </div>
                </TableCell>
                <TableCell
                  className={cn(
                    "px-3 py-3 text-right text-ui font-semibold",
                    pnlVal != null && pnlVal > 0 && "text-[var(--success)]",
                    pnlVal != null && pnlVal < 0 && "text-destructive"
                  )}
                >
                  {displayMoney(pnlVal, { signed: true })}
                </TableCell>
                <TableCell className="whitespace-normal px-3 py-3">
                  <div className="grid grid-cols-2 gap-3">
                    <DenseMetric
                      label={t("journal.openTime")}
                      value={formatTime(trade.open_time)}
                      valueClassName="text-caption font-medium text-muted-foreground"
                    />
                    <DenseMetric
                      label={t("journal.closeTime")}
                      value={formatTime(trade.close_time)}
                      valueClassName="text-caption font-medium text-muted-foreground"
                    />
                  </div>
                </TableCell>
                <TableCell className="px-3 py-3 text-right">
                  <div className="flex justify-end gap-1.5">
                    <Button
                      variant="outline"
                      size={journalTableControlSizes.rowAction}
                      onClick={(e) => { e.stopPropagation(); navigate(`/replay/${trade.id}`); }}
                      aria-label={t("journal.replay")}
                      title={t("journal.replay")}
                    >
                      <Play />
                    </Button>
                    <Button
                      variant="outline"
                      size={journalTableControlSizes.rowAction}
                      onClick={(e) => { e.stopPropagation(); onEdit(trade); }}
                      aria-label={t("journal.edit")}
                      title={t("journal.edit")}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="outline"
                      size={journalTableControlSizes.rowAction}
                      onClick={(e) => { e.stopPropagation(); onDelete(trade.id); }}
                      aria-label={t("journal.delete")}
                      title={t("journal.delete")}
                      className="hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>

              {expanded && hasDetails && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={selection ? 7 : 6} className="whitespace-normal px-3 pb-4 pt-1">
                    <div className="flex flex-col gap-3 rounded-[14px] border border-border bg-[color-mix(in_srgb,var(--chip-bg)_72%,transparent)] p-4">
                      <div className="flex flex-wrap gap-1.5">
                        {trade.setup_type ? <Badge variant="outline">{trade.setup_type}</Badge> : null}
                        {trade.emotional_state ? <Badge variant="outline">{t(`journal.emotion.${trade.emotional_state}`)}</Badge> : null}
                        {trade.confidence != null ? <Badge variant="outline">{t("journal.confidence")}: {trade.confidence}/10</Badge> : null}
                        {trade.execution_quality != null ? <Badge variant="outline">{t("journal.executionQuality")}: {trade.execution_quality}/10</Badge> : null}
                        {trade.compliance.score != null ? <Badge variant="outline">{t("compliance.title")}: {trade.compliance.score}%</Badge> : null}
                      </div>
                      {trade.mistakes.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {trade.mistakes.map((mistake) => <Badge key={mistake} variant="outline" className="text-[var(--danger)]">{t(`journal.mistake.${mistake}`)}</Badge>)}
                        </div>
                      ) : null}
                      {trade.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {trade.tags.map((tag) => (
                            <Badge
                              key={tag}
                              variant="outline"
                              className={cn(
                                "rounded-md",
                                journalTableControlSizes.tagBadgeSurfaceClassName,
                                journalTableControlSizes.tagBadgeText
                              )}
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )}
                      {trade.notes && (
                        <div className="text-caption text-muted-foreground leading-relaxed whitespace-pre-wrap">
                          {trade.notes}
                        </div>
                      )}
                      {hasImages && (
                        <div className="flex gap-2 overflow-x-auto">
                          {trade.images.map((image) => (
                            <button
                              key={image.id}
                              type="button"
                              className="h-20 w-32 shrink-0 overflow-hidden rounded-md border border-border bg-muted"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPreviewImage(image);
                              }}
                            >
                              <img
                                src={authedAssetUrl(image.url)}
                                alt={image.original_name || t("journal.screenshot")}
                                className="h-full w-full object-cover"
                              />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
    <ImageAnnotationDialog
      assetId={previewImage?.asset_id ?? null}
      image={previewImage}
      open={previewImage != null}
      onOpenChange={(open) => !open && setPreviewImage(null)}
    />
    </>
  );
}
