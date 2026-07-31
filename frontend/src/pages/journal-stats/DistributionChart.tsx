import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactECharts from "echarts-for-react";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { journalStatsControlSizes } from "@/pages/journal-ui-config";
import type { TradeStats } from "@/api/client";
import { useJournalSettings } from "@/journal/journal-settings-context";

type View = "bySorted" | "byHour";

interface Props {
  stats: TradeStats;
}

export default function DistributionChart({ stats }: Props) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();
  const [view, setView] = useState<View>("bySorted");

  const option = useMemo(() => {
    const cs = getComputedStyle(document.documentElement);
    const textColor = cs.getPropertyValue("--text-secondary").trim();
    const borderColor = cs.getPropertyValue("--border").trim();
    const success = cs.getPropertyValue("--success").trim();
    const danger = cs.getPropertyValue("--danger").trim();
    const panelBg = cs.getPropertyValue("--panel-bg").trim() || "#1a1a1a";
    const primary = cs.getPropertyValue("--text-primary").trim();

    const colorFor = (v: number) => (v > 0 ? success : v < 0 ? danger : borderColor);

    const baseAxes = {
      xAxis: {
        type: "category" as const,
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
      grid: { left: 56, right: 16, top: 24, bottom: 32 },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        backgroundColor: panelBg,
        borderColor,
        textStyle: { color: primary, fontSize: 12 },
        valueFormatter: (v: unknown) => (typeof v === "number" ? displayMoney(v) : String(v)),
      },
    };

    if (view === "bySorted") {
      const values = stats.distribution_series;
      if (!values.length) return null;
      return {
        ...baseAxes,
        xAxis: {
          ...baseAxes.xAxis,
          data: values.map((_, i) => `${i + 1}`),
        },
        series: [
          {
            type: "bar" as const,
            data: values.map((v) => ({
              value: Number(v.toFixed(2)),
              itemStyle: { color: colorFor(v) },
            })),
            barMaxWidth: 18,
          },
        ],
      };
    }

    // byHour
    const buckets = stats.pnl_by_hour;
    if (!buckets.length) return null;
    const map = new Map<number, { total_pnl: number; count: number }>();
    for (const b of buckets) map.set(b.hour, { total_pnl: b.total_pnl, count: b.count });
    const xs = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0"));
    const data = Array.from({ length: 24 }, (_, h) => {
      const bucket = map.get(h);
      const v = bucket ? bucket.total_pnl : 0;
      return { value: Number(v.toFixed(2)), itemStyle: { color: colorFor(v) } };
    });
    return {
      ...baseAxes,
      xAxis: { ...baseAxes.xAxis, data: xs },
      series: [{ type: "bar" as const, data, barMaxWidth: 18 }],
    };
  }, [displayMoney, stats, view]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-0">
        <CardTitle>{t("journal.chart.distribution")}</CardTitle>
        <CardAction>
          <ToggleGroup
            type="single"
            variant="outline"
            size={journalStatsControlSizes.rangeToggle}
            value={view}
            onValueChange={(v) => {
              if (v) setView(v as View);
            }}
            spacing={1}
          >
            <ToggleGroupItem
              value="bySorted"
              style={{ fontSize: journalStatsControlSizes.fontSize }}
            >
              {t("journal.chart.distribution.bySorted")}
            </ToggleGroupItem>
            <ToggleGroupItem
              value="byHour"
              style={{ fontSize: journalStatsControlSizes.fontSize }}
            >
              {t("journal.chart.distribution.byHour")}
            </ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent>
        {option ? (
          <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: "svg" }} />
        ) : null}
      </CardContent>
    </Card>
  );
}
