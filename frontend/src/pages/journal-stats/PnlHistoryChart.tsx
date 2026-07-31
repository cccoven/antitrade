import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import ReactECharts from "echarts-for-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TradeStats } from "@/api/client";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface Props {
  stats: TradeStats;
}

export default function PnlHistoryChart({ stats }: Props) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();

  const option = useMemo(() => {
    const cs = getComputedStyle(document.documentElement);
    const textColor = cs.getPropertyValue("--text-secondary").trim();
    const borderColor = cs.getPropertyValue("--border").trim();
    const accentColor = cs.getPropertyValue("--accent").trim();
    const success = cs.getPropertyValue("--success").trim();
    const panelBg = cs.getPropertyValue("--panel-bg").trim() || "#1a1a1a";
    const primary = cs.getPropertyValue("--text-primary").trim();
    const textFaint = cs.getPropertyValue("--text-faint").trim() || "#6b7280";

    const series = stats.per_trade_series;
    if (!series.length) return null;

    let cumGross = 0;
    let cumNet = 0;
    const xs: string[] = [];
    const grossData: number[] = [];
    const netData: number[] = [];
    for (const p of series) {
      cumGross += p.pnl_gross;
      cumNet += p.pnl_net;
      xs.push(p.time.slice(0, 10));
      grossData.push(Number(cumGross.toFixed(2)));
      netData.push(Number(cumNet.toFixed(2)));
    }
    return {
      color: [accentColor, success],
      grid: { left: 56, right: 16, top: 40, bottom: 32 },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: panelBg,
        borderColor,
        textStyle: { color: primary, fontSize: 12 },
        valueFormatter: (v: unknown) => (typeof v === "number" ? displayMoney(v) : String(v)),
      },
      legend: {
        top: 0,
        right: 0,
        textStyle: { color: primary, fontSize: 11 },
        inactiveColor: textFaint,
        data: [t("journal.chart.pnlHistory.gross"), t("journal.chart.pnlHistory.net")],
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
          name: t("journal.chart.pnlHistory.gross"),
          type: "line" as const,
          data: grossData,
          smooth: true,
          symbol: "none",
          lineStyle: { color: accentColor, width: 2 },
        },
        {
          name: t("journal.chart.pnlHistory.net"),
          type: "line" as const,
          data: netData,
          smooth: true,
          symbol: "none",
          lineStyle: { color: success, width: 2 },
        },
      ],
    };
  }, [displayMoney, stats, t]);

  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle>{t("journal.chart.pnlHistory")}</CardTitle>
      </CardHeader>
      <CardContent>
        {option ? (
          <ReactECharts option={option} style={{ height: 320 }} opts={{ renderer: "svg" }} />
        ) : null}
      </CardContent>
    </Card>
  );
}
