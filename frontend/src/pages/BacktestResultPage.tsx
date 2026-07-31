import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft, Download, Loader2 } from "lucide-react";
import ReactECharts from "echarts-for-react";
import type {
  BacktestAnalysisResult,
  BacktestResult,
  BacktestRun,
  BacktestRunResult,
} from "@/api/client";
import { getBacktestRun } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import FlushPage from "@/components/FlushPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
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
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import BacktestAnalysisResultPanel from "@/pages/BacktestAnalysisResultPanel";
import { backtestControlSizes } from "@/pages/backtest-ui-config";

function isAnalysisResult(
  value: BacktestRunResult,
): value is BacktestAnalysisResult {
  return "kind" in value;
}

function formatPnl(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function pnlColor(value: number): string {
  if (value > 0) return "var(--success)";
  if (value < 0) return "var(--danger)";
  return "var(--foreground)";
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function downloadText(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <Card className="min-w-0 gap-2 py-3 shadow-none">
      <CardHeader className="px-4 pb-0">
        <div className="truncate text-caption text-muted-foreground">{label}</div>
      </CardHeader>
      <CardContent className="px-4 pt-0">
        <div
          className="truncate text-subheading font-semibold tabular-nums"
          style={{ color: tone }}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function StandardResult({
  result,
}: {
  result: BacktestResult;
}) {
  const { t } = useTranslation();

  const equityOption = useMemo(() => {
    const points = result.equity_curve.filter(
      (point): point is { time: string; equity: number } =>
        Boolean(point.time),
    );
    if (points.length === 0) return null;
    const styles = getComputedStyle(document.documentElement);
    const text = styles.getPropertyValue("--muted-foreground").trim();
    const border = styles.getPropertyValue("--border").trim();
    const accent =
      styles.getPropertyValue("--primary").trim() ||
      styles.getPropertyValue("--accent").trim();
    return {
      grid: { left: 52, right: 18, top: 18, bottom: 34 },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: styles.getPropertyValue("--popover").trim(),
        borderColor: border,
        textStyle: {
          color: styles.getPropertyValue("--popover-foreground").trim(),
          fontSize: 12,
        },
      },
      xAxis: {
        type: "category" as const,
        data: points.map((point) => point.time.slice(0, 10)),
        axisLine: { lineStyle: { color: border } },
        axisLabel: { color: text, fontSize: 10 },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: { color: text, fontSize: 10 },
        splitLine: { lineStyle: { color: border, type: "dashed" as const } },
      },
      series: [{
        type: "line" as const,
        data: points.map((point) => point.equity),
        smooth: true,
        symbol: "none",
        lineStyle: { color: accent, width: 2 },
        areaStyle: { color: accent, opacity: 0.1 },
      }],
    };
  }, [result]);

  const priceOption = useMemo(() => {
    if (!result.price_curve?.length) return null;
    const styles = getComputedStyle(document.documentElement);
    const text = styles.getPropertyValue("--muted-foreground").trim();
    const border = styles.getPropertyValue("--border").trim();
    const success = styles.getPropertyValue("--success").trim() || "#22c55e";
    const danger = styles.getPropertyValue("--danger").trim() || "#ef4444";
    return {
      grid: { left: 58, right: 18, top: 30, bottom: 44 },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: styles.getPropertyValue("--popover").trim(),
        borderColor: border,
        textStyle: {
          color: styles.getPropertyValue("--popover-foreground").trim(),
        },
      },
      legend: {
        top: 0,
        right: 8,
        textStyle: { color: text, fontSize: 10 },
      },
      xAxis: {
        type: "category" as const,
        data: result.price_curve.map((point) => point.time),
        axisLabel: {
          color: text,
          fontSize: 10,
          formatter: (value: string) => value.slice(0, 10),
        },
        axisLine: { lineStyle: { color: border } },
      },
      yAxis: {
        scale: true,
        axisLabel: { color: text, fontSize: 10 },
        splitLine: { lineStyle: { color: border, type: "dashed" as const } },
      },
      dataZoom: [
        { type: "inside" as const },
        { type: "slider" as const, height: 16 },
      ],
      series: [
        {
          name: t("backtest.price"),
          type: "candlestick" as const,
          data: result.price_curve.map((point) => [
            point.open,
            point.close,
            point.low,
            point.high,
          ]),
          itemStyle: {
            color: success,
            color0: danger,
            borderColor: success,
            borderColor0: danger,
          },
        },
        {
          name: t("backtest.entries"),
          type: "scatter" as const,
          symbol: "triangle",
          symbolSize: 10,
          itemStyle: { color: success },
          data: result.trades.map((trade) => [
            trade.entry_time,
            trade.entry_price,
          ]),
        },
        {
          name: t("backtest.exits"),
          type: "scatter" as const,
          symbol: "triangle",
          symbolRotate: 180,
          symbolSize: 10,
          itemStyle: { color: danger },
          data: result.trades.map((trade) => [
            trade.exit_time,
            trade.exit_price,
          ]),
        },
      ],
    };
  }, [result, t]);

  const drawdownOption = useMemo(() => {
    if (!result.drawdown_curve?.length) return null;
    const styles = getComputedStyle(document.documentElement);
    const text = styles.getPropertyValue("--muted-foreground").trim();
    const border = styles.getPropertyValue("--border").trim();
    const danger = styles.getPropertyValue("--danger").trim() || "#ef4444";
    return {
      grid: { left: 58, right: 18, top: 18, bottom: 34 },
      tooltip: { trigger: "axis" as const },
      xAxis: {
        type: "category" as const,
        data: result.drawdown_curve.map((point) => point.time),
        axisLabel: {
          color: text,
          fontSize: 10,
          formatter: (value: string) => value.slice(0, 10),
        },
        axisLine: { lineStyle: { color: border } },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: {
          color: text,
          fontSize: 10,
          formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
        },
        splitLine: { lineStyle: { color: border, type: "dashed" as const } },
      },
      series: [{
        type: "line" as const,
        data: result.drawdown_curve.map((point) => point.drawdown_pct),
        symbol: "none",
        lineStyle: { color: danger, width: 1.5 },
        areaStyle: { color: danger, opacity: 0.12 },
      }],
    };
  }, [result]);

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <MetricCard
          label={t("backtest.totalPnl")}
          value={formatPnl(result.total_pnl)}
          tone={pnlColor(result.total_pnl)}
        />
        <MetricCard
          label={t("backtest.totalReturn")}
          value={formatPct(result.total_return_pct)}
        />
        <MetricCard label={t("backtest.totalTrades")} value={result.total_trades} />
        <MetricCard label={t("backtest.winRate")} value={formatPct(result.win_rate)} />
        <MetricCard
          label={t("backtest.profitFactor")}
          value={result.profit_factor?.toFixed(2) ?? "—"}
        />
        <MetricCard
          label={t("backtest.maxDrawdown")}
          value={
            result.max_drawdown_pct != null
              ? formatPct(result.max_drawdown_pct)
              : formatPnl(result.max_drawdown)
          }
          tone="var(--danger)"
        />
        <MetricCard
          label={t("backtest.sharpeRatio")}
          value={result.sharpe_ratio.toFixed(2)}
        />
        <MetricCard
          label={t("backtest.avgWin")}
          value={formatPnl(result.avg_win)}
          tone={result.avg_win > 0 ? "var(--success)" : undefined}
        />
        <MetricCard
          label={t("backtest.avgLoss")}
          value={formatPnl(result.avg_loss)}
          tone="var(--danger)"
        />
        <MetricCard
          label={t("backtest.winLossRatio")}
          value={result.win_loss_ratio.toFixed(2)}
        />
        <MetricCard
          label={t("backtest.benchmarkReturn")}
          value={formatPct(result.benchmark?.return_pct)}
        />
        <MetricCard
          label={t("backtest.excessReturn")}
          value={
            result.total_return_pct != null &&
            result.benchmark?.return_pct != null
              ? formatPct(
                  result.total_return_pct - result.benchmark.return_pct,
                )
              : "—"
          }
        />
      </div>

      {priceOption ? (
        <Card className="gap-0 overflow-hidden py-0 shadow-none">
          <CardHeader className="border-b border-border/70 bg-muted/10 px-4 py-3">
            <CardTitle className="text-subheading">
              {t("backtest.priceAndTrades")}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3">
            <ReactECharts
              option={priceOption}
              style={{ height: 380 }}
              opts={{ renderer: "svg" }}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-3 xl:grid-cols-2">
        {equityOption ? (
          <Card className="gap-0 overflow-hidden py-0 shadow-none">
            <CardHeader className="border-b border-border/70 bg-muted/10 px-4 py-3">
              <CardTitle className="text-subheading">
                {t("backtest.equityCurve")}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3">
              <ReactECharts
                option={equityOption}
                style={{ height: 260 }}
                opts={{ renderer: "svg" }}
              />
            </CardContent>
          </Card>
        ) : null}
        {drawdownOption ? (
          <Card className="gap-0 overflow-hidden py-0 shadow-none">
            <CardHeader className="border-b border-border/70 bg-muted/10 px-4 py-3">
              <CardTitle className="text-subheading">
                {t("backtest.drawdownCurve")}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3">
              <ReactECharts
                option={drawdownOption}
                style={{ height: 260 }}
                opts={{ renderer: "svg" }}
              />
            </CardContent>
          </Card>
        ) : null}
      </div>

      {result.trades.length > 0 ? (
        <Card className="gap-0 overflow-hidden py-0 shadow-none">
          <CardHeader className="border-b border-border/70 bg-muted/10 px-4 py-3">
            <CardTitle className="text-subheading">
              {t("backtest.tradeDetails", { count: result.trades.length })}
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table className="min-w-[1040px]">
              <TableHeader className="bg-muted/15">
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t("backtest.entryTime")}</TableHead>
                  <TableHead>{t("backtest.exitTime")}</TableHead>
                  <TableHead>{t("backtest.direction")}</TableHead>
                  <TableHead className="text-right">{t("backtest.entryPrice")}</TableHead>
                  <TableHead className="text-right">{t("backtest.exitPrice")}</TableHead>
                  <TableHead className="text-right">{t("backtest.commission")}</TableHead>
                  <TableHead className="text-right">{t("backtest.totalPnl")}</TableHead>
                  <TableHead>{t("backtest.exitReason")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="[&_tr:nth-child(even)]:bg-muted/10">
                {result.trades.slice(0, 100).map((trade, index) => (
                  <TableRow
                    key={`${trade.entry_time}-${trade.exit_time}-${index}`}
                    className="border-b border-border/40 hover:bg-muted/20"
                  >
                    <TableCell className="whitespace-nowrap text-caption text-muted-foreground">
                      {formatDateTime(trade.entry_time)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-caption text-muted-foreground">
                      {formatDateTime(trade.exit_time)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          trade.direction === "long"
                            ? "border-[var(--success)]/25 bg-[var(--success)]/10 text-[var(--success)]"
                            : "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]"
                        }
                      >
                        {t(
                          trade.direction === "long"
                            ? "backtest.directionLong"
                            : "backtest.directionShort",
                        )}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-caption tabular-nums">
                      {trade.entry_price.toFixed(4)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-caption tabular-nums">
                      {trade.exit_price.toFixed(4)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-caption text-muted-foreground tabular-nums">
                      {trade.commission.toFixed(2)}
                    </TableCell>
                    <TableCell
                      className="text-right font-mono text-caption font-semibold tabular-nums"
                      style={{ color: pnlColor(trade.pnl) }}
                    >
                      {formatPnl(trade.pnl)}
                    </TableCell>
                    <TableCell className="text-caption">
                      {t(`backtest.exitReason.${trade.exit_reason}`)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {result.trades.length > 100 ? (
              <p className="border-t border-border/50 px-4 py-3 text-caption text-muted-foreground">
                {t("backtest.tradeLimit", { count: 100 })}
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

export default function BacktestResultPage() {
  const { runId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const { user, loading: authLoading } = useAuth();
  const [run, setRun] = useState<BacktestRun | null>(null);
  const [loadError, setLoadError] = useState(false);

  const loadRun = useCallback(async () => {
    try {
      const detail = await getBacktestRun(runId);
      setRun(detail);
      setLoadError(false);
      return detail;
    } catch {
      setLoadError(true);
      return null;
    }
  }, [runId]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    let timer: number | undefined;

    const refresh = async () => {
      const detail = await loadRun();
      if (
        active &&
        detail &&
        (detail.status === "queued" || detail.status === "running")
      ) {
        timer = window.setTimeout(refresh, 2000);
      }
    };
    refresh();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [loadRun, user]);

  const standardResult =
    run?.result && !isAnalysisResult(run.result)
      ? (run.result as BacktestResult)
      : null;

  const btnStyle = {
    fontSize: backtestControlSizes.fontSize,
    fontWeight: backtestControlSizes.fontWeight,
  };
  const backTarget =
    searchParams.get("from") === "history"
      ? "/backtest?tab=history"
      : "/backtest";

  const exportResultJson = () => {
    if (!run?.result) return;
    downloadText(
      `${run.strategy_name || "backtest"}-result.json`,
      JSON.stringify(run.result, null, 2),
      "application/json;charset=utf-8",
    );
  };

  const exportTradesCsv = () => {
    if (!standardResult) return;
    const headers = [
      "entry_time",
      "exit_time",
      "direction",
      "entry_price",
      "exit_price",
      "size",
      "pnl",
      "commission",
      "return_pct",
      "exit_reason",
    ];
    const rows = standardResult.trades.map((trade) =>
      headers.map((key) => csvCell(trade[key as keyof typeof trade])).join(","),
    );
    downloadText(
      `${run?.strategy_name || "backtest"}-trades.csv`,
      [headers.join(","), ...rows].join("\n"),
      "text/csv;charset=utf-8",
    );
  };

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  return (
    <FlushPage
      contentClassName="gap-3 p-3 md:p-4"
      toolbar={
        <div className="flex min-w-0 items-center gap-2">
          <TooltipIconButton
            label={t("backtest.backToBacktest")}
            variant="ghost"
            size="icon-sm"
            style={btnStyle}
            asChild
          >
            <Link to={backTarget}>
              <ChevronLeft className="size-[var(--icon-md)]" />
            </Link>
          </TooltipIconButton>
          <span className="h-4 w-px bg-border" aria-hidden="true" />
          <div className="min-w-0">
            <div className="truncate text-ui font-medium">
              {run?.strategy_name || t("backtest.result")}
            </div>
            {run ? (
              <div className="truncate text-micro text-muted-foreground">
                {run.strategy_config.symbol} · {run.strategy_config.interval} ·{" "}
                {t(`backtest.runKind.${run.run_kind}`)}
              </div>
            ) : null}
          </div>
        </div>
      }
      toolbarAside={
        run?.status === "completed" && run.result ? (
          <div className="flex items-center gap-2">
            {standardResult ? (
              <Button
                variant="outline"
                size="sm"
                style={btnStyle}
                onClick={exportTradesCsv}
              >
                <Download />
                {t("backtest.exportCsv")}
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              style={btnStyle}
              onClick={exportResultJson}
            >
              <Download />
              {t("backtest.exportJson")}
            </Button>
          </div>
        ) : null
      }
    >
      {loadError ? (
        <Empty className="min-h-[320px] border border-dashed border-border">
          <EmptyHeader>
            <EmptyTitle>{t("backtest.resultLoadFailed")}</EmptyTitle>
            <EmptyDescription>{t("backtest.resultLoadFailedHint")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : !run || run.status === "queued" || run.status === "running" ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
          <div className="text-ui text-muted-foreground">
            {t("backtest.running")}
          </div>
        </div>
      ) : run.status === "failed" ? (
        <Empty className="min-h-[320px] border border-dashed border-border">
          <EmptyHeader>
            <EmptyTitle>{t("backtest.runFailed")}</EmptyTitle>
            <EmptyDescription>
              {run.error || t("backtest.runFailedHint")}
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : run.result && isAnalysisResult(run.result) ? (
        <BacktestAnalysisResultPanel result={run.result} t={t} />
      ) : standardResult ? (
        <StandardResult result={standardResult} />
      ) : (
        <Empty className="min-h-[320px] border border-dashed border-border">
          <EmptyHeader>
            <EmptyTitle>{t("backtest.noResult")}</EmptyTitle>
          </EmptyHeader>
        </Empty>
      )}
    </FlushPage>
  );
}
