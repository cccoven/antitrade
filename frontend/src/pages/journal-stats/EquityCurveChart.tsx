import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import ReactECharts from "echarts-for-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TradeStats } from "@/api/client";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface Props {
  stats: TradeStats;
  startingCapital: number;
}

export default function EquityCurveChart({ stats, startingCapital }: Props) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();

  const option = useMemo(() => {
    const cs = getComputedStyle(document.documentElement);
    const textColor = cs.getPropertyValue("--text-secondary").trim();
    const borderColor = cs.getPropertyValue("--border").trim();
    const success = cs.getPropertyValue("--success").trim() || "#4ade80";
    const danger = cs.getPropertyValue("--danger").trim() || "#ef4444";
    const accent = cs.getPropertyValue("--accent").trim() || "#b88352";
    const panelBg = cs.getPropertyValue("--panel-bg").trim() || "#1a1a1a";
    const primary = cs.getPropertyValue("--text-primary").trim();
    const textFaint = cs.getPropertyValue("--text-faint").trim() || "#6b7280";

    const anchor = startingCapital + stats.pnl_before_range;
    const series = stats.per_trade_series;

    // Group trades by date (YYYY-MM-DD). per_trade_series is already in
    // chronological close_time order, so buckets preserve intra-day order too.
    const byDate = new Map<string, number[]>();
    for (const p of series) {
      const date = p.time.slice(0, 10);
      if (!byDate.has(date)) byDate.set(date, []);
      byDate.get(date)!.push(p.pnl_net);
    }
    const dates = Array.from(byDate.keys()).sort();

    const xs: string[] = [t("journal.startingCapital.anchor")];
    const closes: number[] = [Number(anchor.toFixed(2))];
    const lows: number[] = [Number(anchor.toFixed(2))];
    const highs: number[] = [Number(anchor.toFixed(2))];

    let running = anchor;
    for (const date of dates) {
      let dayLow = running; // running = day's opening balance
      let dayHigh = running;
      for (const pnl of byDate.get(date)!) {
        running += pnl;
        if (running < dayLow) dayLow = running;
        if (running > dayHigh) dayHigh = running;
      }
      xs.push(date);
      closes.push(Number(running.toFixed(2)));
      lows.push(Number(dayLow.toFixed(2)));
      highs.push(Number(dayHigh.toFixed(2)));
    }

    // Chart composition: balance + maximum hug the top, minimum hugs the
    // bottom. Small padding above max; generous padding below min. Snap the
    // bounds to a "nice" step (10^n × 5) so ECharts' tick lines align exactly
    // with yMin/yMax — otherwise a ghost splitline appears at the boundary.
    const globalMin = Math.min(...closes, ...lows);
    const globalMax = Math.max(...closes, ...highs);
    const amplitude = Math.max(globalMax - globalMin, 100);
    const magnitude = Math.pow(10, Math.floor(Math.log10(amplitude)));
    const step = magnitude * 5;
    const yMin = Math.floor((globalMin - amplitude * 1.5) / step) * step;
    const yMax = Math.ceil((globalMax + amplitude * 0.3) / step) * step;

    const balanceLabel = t("journal.chart.equityCurve.balance");
    const maximumLabel = t("journal.chart.equityCurve.maximum");
    const minimumLabel = t("journal.chart.equityCurve.minimum");

    return {
      color: [success, accent, danger],
      grid: { left: 72, right: 16, top: 40, bottom: 48 },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: panelBg,
        borderColor,
        textStyle: { color: primary, fontSize: 12 },
        valueFormatter: (v: unknown) =>
          typeof v === "number" ? displayMoney(v) : String(v),
      },
      legend: {
        top: 0,
        right: 0,
        textStyle: { color: primary, fontSize: 11 },
        inactiveColor: textFaint,
        data: [balanceLabel, maximumLabel, minimumLabel],
      },
      xAxis: {
        type: "category" as const,
        data: xs,
        axisLine: { lineStyle: { color: borderColor } },
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value" as const,
        min: yMin,
        max: yMax,
        interval: step,
        axisLine: { show: false },
        axisLabel: {
          color: textColor,
          fontSize: 10,
          formatter: (v: number) => displayMoney(v),
        },
        splitLine: { lineStyle: { color: borderColor, type: "dashed" as const } },
      },
      series: [
        {
          name: balanceLabel,
          type: "line" as const,
          data: closes,
          smooth: true,
          symbol: "none",
          lineStyle: { color: success, width: 2 },
          areaStyle: {
            color: {
              type: "linear" as const,
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: success + "55" },
                { offset: 1, color: success + "00" },
              ],
            },
          },
        },
        {
          name: maximumLabel,
          type: "line" as const,
          data: highs,
          smooth: true,
          symbol: "none",
          lineStyle: { color: accent, width: 1.5, type: "dashed" as const },
        },
        {
          name: minimumLabel,
          type: "line" as const,
          data: lows,
          smooth: true,
          symbol: "none",
          lineStyle: { color: danger, width: 1.5, type: "dashed" as const },
        },
      ],
    };
  }, [displayMoney, stats, startingCapital, t]);

  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle>{t("journal.chart.equityCurve")}</CardTitle>
      </CardHeader>
      <CardContent>
        <ReactECharts option={option} style={{ height: 320 }} opts={{ renderer: "svg" }} />
      </CardContent>
    </Card>
  );
}
