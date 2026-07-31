import type { TFunction } from "i18next";
import type {
  BacktestAnalysisResult,
} from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function percent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function metricGrid(
  metrics: {
    total_return_pct?: number;
    sharpe_ratio: number;
    max_drawdown_pct?: number;
    total_trades: number;
  },
  t: TFunction,
) {
  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-1 text-caption">
      <span className="text-muted-foreground">{t("backtest.totalReturn")}</span>
      <span>{percent(metrics.total_return_pct ?? 0)}</span>
      <span className="text-muted-foreground">{t("backtest.sharpeRatio")}</span>
      <span>{metrics.sharpe_ratio.toFixed(2)}</span>
      <span className="text-muted-foreground">{t("backtest.maxDrawdown")}</span>
      <span>{percent(metrics.max_drawdown_pct ?? 0)}</span>
      <span className="text-muted-foreground">{t("backtest.totalTrades")}</span>
      <span>{metrics.total_trades}</span>
    </div>
  );
}

export default function BacktestAnalysisResultPanel({
  result,
  t,
}: {
  result: BacktestAnalysisResult;
  t: TFunction;
}) {
  if (result.kind === "validation") {
    const train = result.train_result;
    const test = result.test_result;
    return (
      <Card className="gap-0 overflow-hidden py-0">
        <CardHeader className="border-b border-border bg-muted/15 px-4 py-3">
          <CardTitle className="text-subheading">
            {t("backtest.validationResult")}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 md:grid-cols-2">
          <div className="rounded-md border border-border p-3">
            <div className="mb-2 text-ui font-medium">
              {t("backtest.inSample")}
            </div>
            {metricGrid(train, t)}
          </div>
          <div className="rounded-md border border-border p-3">
            <div className="mb-2 text-ui font-medium">
              {t("backtest.outOfSample")}
            </div>
            {metricGrid(test, t)}
          </div>
          <div className="text-caption text-muted-foreground md:col-span-2">
            {t("backtest.splitAt")}: {result.split_time}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (result.kind === "optimization") {
    return (
      <Card className="gap-0 overflow-hidden py-0">
        <CardHeader className="border-b border-border bg-muted/15 px-4 py-3">
          <CardTitle className="text-subheading">
            {t("backtest.optimizationResult", { count: result.trial_count })}
          </CardTitle>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(result.best_parameters).map(([key, value]) => (
              <Badge key={key} variant="outline">
                {t(`backtest.parameter.${key}`)}: {value}
              </Badge>
            ))}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("backtest.parameters")}</TableHead>
                <TableHead>{t("backtest.totalReturn")}</TableHead>
                <TableHead>{t("backtest.sharpeRatio")}</TableHead>
                <TableHead>{t("backtest.maxDrawdown")}</TableHead>
                <TableHead>{t("backtest.totalTrades")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.trials.map((trial, index) => (
                <TableRow key={index}>
                  <TableCell className="text-caption">
                    {Object.entries(trial.parameters)
                      .map(([key, value]) => `${key}=${value}`)
                      .join(", ")}
                  </TableCell>
                  <TableCell>{percent(trial.metrics.total_return_pct)}</TableCell>
                  <TableCell>{trial.metrics.sharpe_ratio.toFixed(2)}</TableCell>
                  <TableCell>{percent(trial.metrics.max_drawdown_pct)}</TableCell>
                  <TableCell>{trial.metrics.total_trades}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="border-b border-border bg-muted/15 px-4 py-3">
        <CardTitle className="text-subheading">
          {t("backtest.walkForwardResult", { count: result.window_count })}
        </CardTitle>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">
            {t("backtest.compoundedReturn")}:{" "}
            {percent(result.summary.compounded_test_return_pct)}
          </Badge>
          <Badge variant="outline">
            {t("backtest.profitableWindows")}:{" "}
            {result.summary.profitable_windows}/{result.window_count}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("backtest.testPeriod")}</TableHead>
              <TableHead>{t("backtest.bestParameters")}</TableHead>
              <TableHead>{t("backtest.inSampleReturn")}</TableHead>
              <TableHead>{t("backtest.outOfSampleReturn")}</TableHead>
              <TableHead>{t("backtest.totalTrades")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.windows.map((window, index) => (
              <TableRow key={`${window.test_start}-${index}`}>
                <TableCell className="whitespace-nowrap text-caption">
                  {window.test_start.slice(0, 10)} – {window.test_end.slice(0, 10)}
                </TableCell>
                <TableCell className="text-caption">
                  {Object.entries(window.best_parameters)
                    .map(([key, value]) => `${key}=${value}`)
                    .join(", ")}
                </TableCell>
                <TableCell>{percent(window.train_metrics.total_return_pct)}</TableCell>
                <TableCell>{percent(window.test_metrics.total_return_pct)}</TableCell>
                <TableCell>{window.test_metrics.total_trades}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
