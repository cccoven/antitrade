import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import ReactECharts from "echarts-for-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TradeStats } from "@/api/client";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface Props {
  stats: TradeStats;
}

export default function CompositionCharts({ stats }: Props) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();

  const winLossOption = useMemo(() => {
    const cs = typeof document !== "undefined" ? getComputedStyle(document.documentElement) : null;
    const success = cs?.getPropertyValue("--success").trim() || "#4ade80";
    const danger = cs?.getPropertyValue("--danger").trim() || "#ef4444";
    const muted = cs?.getPropertyValue("--border").trim() || "#6b7280";
    const textPrimary = cs?.getPropertyValue("--text-primary").trim() || "#e5e5e5";
    const textFaint = cs?.getPropertyValue("--text-faint").trim() || "#6b7280";
    const total = stats.winners + stats.losers + stats.breakeven_trades;
    if (total === 0) return null;
    return {
      tooltip: { trigger: "item" as const },
      legend: {
        bottom: 0,
        left: "center",
        textStyle: { fontSize: 11, color: textPrimary },
        inactiveColor: textFaint,
      },
      series: [
        {
          type: "pie" as const,
          radius: ["40%", "70%"],
          avoidLabelOverlap: true,
          label: { show: false },
          data: [
            { name: t("journal.kpi.profit.numWinners"), value: stats.winners, itemStyle: { color: success } },
            { name: t("journal.kpi.loss.numLosers"), value: stats.losers, itemStyle: { color: danger } },
            { name: t("journal.chart.composition.winLossBreakeven"), value: stats.breakeven_trades, itemStyle: { color: muted } },
          ],
        },
      ],
    };
  }, [stats, t]);

  const grossLossOption = useMemo(() => {
    const cs = typeof document !== "undefined" ? getComputedStyle(document.documentElement) : null;
    const danger = cs?.getPropertyValue("--danger").trim() || "#ef4444";
    const accent = cs?.getPropertyValue("--accent").trim() || "#b88352";
    const textPrimary = cs?.getPropertyValue("--text-primary").trim() || "#e5e5e5";
    const textFaint = cs?.getPropertyValue("--text-faint").trim() || "#6b7280";
    const tradeLoss = Math.abs(stats.total_loss);
    const commission = stats.total_fees;
    const total = tradeLoss + commission;
    if (total === 0) return null;
    return {
      tooltip: {
        trigger: "item" as const,
        valueFormatter: (v: unknown) =>
          typeof v === "number" ? displayMoney(v) : String(v),
      },
      legend: {
        bottom: 0,
        left: "center",
        textStyle: { fontSize: 11, color: textPrimary },
        inactiveColor: textFaint,
      },
      series: [
        {
          type: "pie" as const,
          radius: ["40%", "70%"],
          avoidLabelOverlap: true,
          label: { show: false },
          data: [
            { name: t("journal.chart.composition.tradeLoss"), value: Number(tradeLoss.toFixed(2)), itemStyle: { color: danger } },
            { name: t("journal.chart.composition.commission"), value: Number(commission.toFixed(2)), itemStyle: { color: accent } },
          ],
        },
      ],
    };
  }, [displayMoney, stats, t]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-0">
          <CardTitle>{t("journal.chart.composition.winLossBreakeven")}</CardTitle>
        </CardHeader>
        <CardContent>
          {winLossOption ? (
            <ReactECharts option={winLossOption} style={{ height: 240 }} opts={{ renderer: "svg" }} />
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-0">
          <CardTitle>{t("journal.chart.composition.grossLoss")}</CardTitle>
        </CardHeader>
        <CardContent>
          {grossLossOption ? (
            <ReactECharts option={grossLossOption} style={{ height: 240 }} opts={{ renderer: "svg" }} />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
