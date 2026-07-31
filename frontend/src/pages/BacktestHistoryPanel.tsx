import {
  ChevronLeft,
  ChevronRight,
  Eye,
  GitCompareArrows,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useEffect, useState, type CSSProperties } from "react";
import type { TFunction } from "i18next";
import type { BacktestResult, BacktestRun } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface BacktestHistoryPanelProps {
  runs: BacktestRun[];
  page: number;
  pageSize: number;
  total: number;
  compareRuns: BacktestRun[];
  busyRunId: string | null;
  buttonStyle: CSSProperties;
  t: TFunction;
  onOpen: (run: BacktestRun) => void;
  onRerun: (run: BacktestRun) => void;
  onCompare: (run: BacktestRun) => void;
  onDelete: (run: BacktestRun) => void;
  onPageChange: (page: number) => void;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function standardResult(run: BacktestRun | undefined): BacktestResult | null {
  return run?.run_kind === "standard" && run.result
    ? (run.result as BacktestResult)
    : null;
}

type ComparisonDirection = "higher" | "lower" | "neutral";

type ComparisonMetric = {
  label: string;
  left: number | null | undefined;
  right: number | null | undefined;
  direction: ComparisonDirection;
  format: (value: number | null | undefined, signed?: boolean) => string;
};

function decimal(
  value: number | null | undefined,
  signed = false,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${signed && value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function percent(
  value: number | null | undefined,
  signed = false,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${signed && value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function integer(
  value: number | null | undefined,
  signed = false,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${signed && value > 0 ? "+" : ""}${Math.round(value)}`;
}

function comparisonTone(
  value: number | null | undefined,
  other: number | null | undefined,
  direction: ComparisonDirection,
): string {
  if (direction === "neutral" || value == null || other == null) {
    return "text-foreground";
  }
  if (value === other) return "text-muted-foreground";
  const better = direction === "higher" ? value > other : value < other;
  return better ? "text-[var(--success)]" : "text-[var(--danger)]";
}

function statusBadgeClass(status: BacktestRun["status"]): string {
  switch (status) {
    case "completed":
      return "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]";
    case "running":
      return "border-primary/30 bg-primary/10 text-primary";
    case "failed":
      return "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]";
    default:
      return "border-border bg-muted/40 text-muted-foreground";
  }
}

export default function BacktestHistoryPanel({
  runs,
  page,
  pageSize,
  total,
  compareRuns,
  busyRunId,
  buttonStyle,
  t,
  onOpen,
  onRerun,
  onCompare,
  onDelete,
  onPageChange,
}: BacktestHistoryPanelProps) {
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const rangeStart = total === 0 ? 0 : page * pageSize + 1;
  const rangeEnd = Math.min((page + 1) * pageSize, total);
  const leftResult = standardResult(compareRuns[0]);
  const rightResult = standardResult(compareRuns[1]);
  const comparisonMetrics: ComparisonMetric[] =
    leftResult && rightResult
      ? [
          {
            label: t("backtest.totalPnl"),
            left: leftResult.total_pnl,
            right: rightResult.total_pnl,
            direction: "higher",
            format: decimal,
          },
          {
            label: t("backtest.totalReturn"),
            left: leftResult.total_return_pct,
            right: rightResult.total_return_pct,
            direction: "higher",
            format: percent,
          },
          {
            label: t("backtest.winRate"),
            left: leftResult.win_rate,
            right: rightResult.win_rate,
            direction: "higher",
            format: percent,
          },
          {
            label: t("backtest.profitFactor"),
            left: leftResult.profit_factor,
            right: rightResult.profit_factor,
            direction: "higher",
            format: decimal,
          },
          {
            label: t("backtest.maxDrawdown"),
            left:
              leftResult.max_drawdown_pct == null
                ? undefined
                : Math.abs(leftResult.max_drawdown_pct),
            right:
              rightResult.max_drawdown_pct == null
                ? undefined
                : Math.abs(rightResult.max_drawdown_pct),
            direction: "lower",
            format: percent,
          },
          {
            label: t("backtest.sharpeRatio"),
            left: leftResult.sharpe_ratio,
            right: rightResult.sharpe_ratio,
            direction: "higher",
            format: decimal,
          },
          {
            label: t("backtest.winLossRatio"),
            left: leftResult.win_loss_ratio,
            right: rightResult.win_loss_ratio,
            direction: "higher",
            format: decimal,
          },
          {
            label: t("backtest.totalTrades"),
            left: leftResult.total_trades,
            right: rightResult.total_trades,
            direction: "neutral",
            format: integer,
          },
        ]
      : [];

  useEffect(() => {
    setComparisonOpen(compareRuns.length === 2);
  }, [compareRuns.length]);

  return (
    <>
    <Card className="gap-0 overflow-hidden py-0 shadow-none">
      <CardHeader className="border-b border-border/70 bg-muted/10 px-4 py-2.5">
        <CardTitle className="text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {t("backtest.history")}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {compareRuns.length > 0 ? (
          <div className="flex items-center justify-between gap-3 border-b border-border bg-muted/10 px-3 py-2">
            <div className="min-w-0">
              <div className="text-ui font-medium">
                {t("backtest.comparisonSelection", {
                  count: compareRuns.length,
                })}
              </div>
              <div className="truncate text-caption text-muted-foreground">
                {compareRuns.map((run) => run.strategy_name).join(" · ")}
              </div>
            </div>
            {compareRuns.length === 2 ? (
              <Button
                variant="outline"
                size="sm"
                style={buttonStyle}
                className="shrink-0"
                onClick={() => setComparisonOpen(true)}
              >
                <GitCompareArrows />
                {t("backtest.viewComparison")}
              </Button>
            ) : (
              <div className="shrink-0 text-caption text-muted-foreground">
                {t("backtest.comparisonHint")}
              </div>
            )}
          </div>
        ) : null}

        {runs.length === 0 ? (
          <div className="px-4 py-8 text-center text-caption text-muted-foreground">
            {t("backtest.noHistory")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table className="min-w-[920px]">
              <TableHeader className="bg-muted/15">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-9 px-3 text-micro font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {t("backtest.strategyName")}
                  </TableHead>
                  <TableHead className="h-9 w-[112px] px-3 text-micro font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {t("backtest.status")}
                  </TableHead>
                  <TableHead className="h-9 px-3 text-micro font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {t("backtest.period")}
                  </TableHead>
                  <TableHead className="h-9 w-[220px] px-3 text-micro font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {t("backtest.createdAt")}
                  </TableHead>
                  <TableHead className="h-9 w-[156px] px-3 text-right text-micro font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {t("common.actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const canRead = run.status === "completed";
                  const canDelete = run.status === "completed" || run.status === "failed";
                  const isCompared = compareRuns.some(
                    (comparedRun) => comparedRun.id === run.id,
                  );
                  return (
                    <TableRow
                      key={run.id}
                      className="border-b border-border/40 hover:bg-muted/15"
                    >
                      <TableCell className="px-3 py-2.5">
                        <div className="max-w-[220px] truncate text-ui font-medium">
                          {run.strategy_name}
                        </div>
                        <div className="text-micro text-muted-foreground">
                          {run.strategy_config.symbol} · {run.strategy_config.interval} ·{" "}
                          {t(`backtest.runKind.${run.run_kind}`)}
                        </div>
                      </TableCell>
                      <TableCell className="px-3 py-2.5">
                        <Badge
                          variant="outline"
                          className={`font-normal text-caption ${statusBadgeClass(run.status)}`}
                        >
                          {t(`backtest.status.${run.status}`)}
                        </Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap px-3 py-2.5 text-caption text-muted-foreground">
                        {run.requested_date_from || "—"} – {run.requested_date_to || "—"}
                      </TableCell>
                      <TableCell className="whitespace-nowrap px-3 py-2.5 text-caption text-muted-foreground">
                        {formatDate(run.created_at)}
                      </TableCell>
                      <TableCell className="px-3 py-2.5">
                        <div className="flex justify-end gap-1">
                          <TooltipIconButton
                            label={t("backtest.openResult")}
                            variant="ghost"
                            size="icon-xs"
                            style={buttonStyle}
                            disabled={!canRead || busyRunId === run.id}
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => onOpen(run)}
                          >
                            <Eye />
                          </TooltipIconButton>
                          <TooltipIconButton
                            label={t(
                              isCompared
                                ? "backtest.removeFromComparison"
                                : "backtest.compare",
                            )}
                            variant="ghost"
                            size="icon-xs"
                            style={buttonStyle}
                            disabled={
                              !canRead ||
                              run.run_kind !== "standard" ||
                              busyRunId === run.id
                            }
                            aria-pressed={isCompared}
                            className={
                              isCompared
                                ? "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary"
                                : "text-muted-foreground hover:text-foreground"
                            }
                            onClick={() => onCompare(run)}
                          >
                            <GitCompareArrows />
                          </TooltipIconButton>
                          <TooltipIconButton
                            label={t("backtest.rerun")}
                            variant="ghost"
                            size="icon-xs"
                            style={buttonStyle}
                            disabled={!canRead || busyRunId === run.id}
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => onRerun(run)}
                          >
                            <RotateCcw />
                          </TooltipIconButton>
                          <TooltipIconButton
                            label={t("common.delete")}
                            variant="ghost"
                            size="icon-xs"
                            style={buttonStyle}
                            disabled={!canDelete || busyRunId === run.id}
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => onDelete(run)}
                          >
                            <Trash2 />
                          </TooltipIconButton>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
        {total > 0 ? (
          <div className="flex items-center justify-between border-t border-border/70 bg-muted/5 px-3 py-2">
            <span className="text-caption tabular-nums text-muted-foreground">
              {rangeStart}–{rangeEnd} / {total}
            </span>
            <div className="flex items-center gap-1">
              <TooltipIconButton
                label={t("backtest.previousPage")}
                variant="outline"
                size="icon-xs"
                style={buttonStyle}
                disabled={page === 0}
                onClick={() => onPageChange(page - 1)}
              >
                <ChevronLeft />
              </TooltipIconButton>
              <TooltipIconButton
                label={t("backtest.nextPage")}
                variant="outline"
                size="icon-xs"
                style={buttonStyle}
                disabled={rangeEnd >= total}
                onClick={() => onPageChange(page + 1)}
              >
                <ChevronRight />
              </TooltipIconButton>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
    <Dialog open={comparisonOpen} onOpenChange={setComparisonOpen}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-[820px]">
        <DialogHeader>
          <DialogTitle>{t("backtest.comparisonTitle")}</DialogTitle>
          <DialogDescription className="text-caption">
            {t("backtest.comparisonDescription")}
          </DialogDescription>
        </DialogHeader>
        {compareRuns.length === 2 && leftResult && rightResult ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table>
              <TableHeader className="bg-muted/20">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[180px]">
                    {t("backtest.comparisonMetric")}
                  </TableHead>
                  {compareRuns.map((run) => (
                    <TableHead key={run.id}>
                      <div className="max-w-[220px] truncate text-foreground">
                        {run.strategy_name}
                      </div>
                      <div className="font-normal text-micro text-muted-foreground">
                        {run.strategy_config.symbol} · {run.strategy_config.interval}
                      </div>
                    </TableHead>
                  ))}
                  <TableHead className="w-[120px] text-right">
                    {t("backtest.difference")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {comparisonMetrics.map((metric) => {
                  const difference =
                    metric.left == null || metric.right == null
                      ? undefined
                      : metric.right - metric.left;
                  return (
                    <TableRow key={metric.label}>
                      <TableCell className="font-medium">
                        {metric.label}
                      </TableCell>
                      <TableCell
                        className={`font-mono font-semibold tabular-nums ${comparisonTone(
                          metric.left,
                          metric.right,
                          metric.direction,
                        )}`}
                      >
                        {metric.format(metric.left)}
                      </TableCell>
                      <TableCell
                        className={`font-mono font-semibold tabular-nums ${comparisonTone(
                          metric.right,
                          metric.left,
                          metric.direction,
                        )}`}
                      >
                        {metric.format(metric.right)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-mono font-semibold tabular-nums ${comparisonTone(
                          metric.right,
                          metric.left,
                          metric.direction,
                        )}`}
                      >
                        {metric.format(difference, true)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
    </>
  );
}
