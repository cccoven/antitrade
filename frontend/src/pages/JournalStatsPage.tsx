import { Fragment, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactECharts from "echarts-for-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { CalendarIcon } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import JournalTradingCalendarCard from "@/components/JournalTradingCalendarCard";
import { journalStatsControlSizes } from "@/pages/journal-ui-config";
import KpiRow from "./journal-stats/KpiRow";
import KpiDetailPanel from "./journal-stats/KpiDetailPanel";
import PnlHistoryChart from "./journal-stats/PnlHistoryChart";
import DistributionChart from "./journal-stats/DistributionChart";
import CompositionCharts from "./journal-stats/CompositionCharts";
import StartingCapitalButton from "./journal-stats/StartingCapitalButton";
import EquityCurveChart from "./journal-stats/EquityCurveChart";
import { useJournalSettings } from "./journal-stats/useJournalSettings";
import { formatPct } from "./journal-stats/journal-stats-format";
import {
  fetchTradeStats,
  type TradeStats,
  type GroupStats,
} from "@/api/client";

type RangePreset =
  | "all"
  | "yesterday"
  | "thisWeek"
  | "lastWeek"
  | "thisMonth"
  | "lastMonth"
  | "thisQuarter"
  | "lastQuarter"
  | "thisYear"
  | "lastYear"
  | "custom";
type DimensionTab = "symbol" | "direction" | "tag";

const PRESET_ORDER: RangePreset[] = [
  "all",
  "yesterday",
  "thisWeek",
  "lastWeek",
  "thisMonth",
  "lastMonth",
  "thisQuarter",
  "lastQuarter",
  "thisYear",
  "lastYear",
  "custom",
];

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}
function endOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
}
function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function computePresetRange(
  preset: Exclude<RangePreset, "custom" | "all">,
  today: Date = new Date(),
): { from: Date; to: Date } {
  const t = startOfDay(today);
  const endToday = endOfDay(today);
  switch (preset) {
    case "yesterday": {
      const y = addDays(t, -1);
      return { from: y, to: endOfDay(y) };
    }
    case "thisWeek": {
      const daysSinceMon = (t.getDay() + 6) % 7;
      return { from: addDays(t, -daysSinceMon), to: endToday };
    }
    case "lastWeek": {
      const daysSinceMon = (t.getDay() + 6) % 7;
      const lastMon = addDays(t, -daysSinceMon - 7);
      return { from: lastMon, to: endOfDay(addDays(lastMon, 6)) };
    }
    case "thisMonth":
      return { from: new Date(t.getFullYear(), t.getMonth(), 1), to: endToday };
    case "lastMonth":
      return {
        from: new Date(t.getFullYear(), t.getMonth() - 1, 1),
        to: endOfDay(new Date(t.getFullYear(), t.getMonth(), 0)),
      };
    case "thisQuarter": {
      const q = Math.floor(t.getMonth() / 3);
      return { from: new Date(t.getFullYear(), q * 3, 1), to: endToday };
    }
    case "lastQuarter": {
      const q = Math.floor(t.getMonth() / 3);
      const year = q === 0 ? t.getFullYear() - 1 : t.getFullYear();
      const lastQ = (q + 3) % 4;
      return {
        from: new Date(year, lastQ * 3, 1),
        to: endOfDay(new Date(year, lastQ * 3 + 3, 0)),
      };
    }
    case "thisYear":
      return { from: new Date(t.getFullYear(), 0, 1), to: endToday };
    case "lastYear":
      return {
        from: new Date(t.getFullYear() - 1, 0, 1),
        to: endOfDay(new Date(t.getFullYear() - 1, 11, 31)),
      };
  }
}

function formatRangeLabel(from: Date, to: Date): string {
  const fmt = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };
  return `${fmt(from)} ~ ${fmt(to)}`;
}

function dimensionKey(item: GroupStats): string {
  for (const k of Object.keys(item)) {
    if (k !== "count" && k !== "total_pnl" && k !== "win_rate") return String(item[k]);
  }
  return "-";
}

// Backend weekday: 0=Mon..6=Sun (Python weekday()).
// EN: Sun first; ZH: Mon first, Sun last.
const WEEKDAY_ORDER_EN = [6, 0, 1, 2, 3, 4, 5]; // Sun, Mon..Sat
const WEEKDAY_ORDER_ZH = [0, 1, 2, 3, 4, 5, 6]; // Mon..Sun
const WEEKDAY_LABELS_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAY_LABELS_ZH = ["一", "二", "三", "四", "五", "六", "日"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function HeatmapGrid({
  data,
  t,
  weekdayLabels,
  weekdayOrder,
}: {
  data: { weekday: number; hour: number; trades: number; wins: number }[];
  t: (key: string, opts?: Record<string, string | number>) => string;
  weekdayLabels: string[];
  weekdayOrder: number[];
}) {
  const cellMap = useMemo(() => {
    const map = new Map<string, { trades: number; wins: number }>();
    for (const d of data) {
      map.set(`${d.weekday}-${d.hour}`, { trades: d.trades, wins: d.wins });
    }
    return map;
  }, [data]);

  return (
    <div className="overflow-x-auto">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `40px repeat(24, 1fr)`,
          gap: 2,
        }}
      >
        {/* Hour header row */}
        <div />
        {HOURS.map((h) => (
          <div key={h} className="text-micro text-muted-foreground text-center">
            {h}
          </div>
        ))}

        {/* Weekday rows */}
        {weekdayLabels.map((label, displayIdx) => {
          const backendWeekday = weekdayOrder[displayIdx];
          return (
          <Fragment key={displayIdx}>
            <div className="text-micro text-muted-foreground flex items-center">
              {label}
            </div>
            {HOURS.map((h) => {
              const cell = cellMap.get(`${backendWeekday}-${h}`);
              if (!cell || cell.trades === 0) {
                return (
                  <div
                    key={`${displayIdx}-${h}`}
                    className="bg-muted rounded-sm"
                    style={{ aspectRatio: "1", minHeight: 18 }}
                  />
                );
              }
              const winRate = cell.wins / cell.trades;
              const losses = cell.trades - cell.wins;
              const pct = winRate >= 0.5
                ? `${30 + winRate * 50}%`
                : `${30 + (1 - winRate) * 50}%`;
              const bg = winRate >= 0.5
                ? `color-mix(in srgb, var(--success) ${pct}, var(--chip-bg))`
                : `color-mix(in srgb, var(--danger) ${pct}, var(--chip-bg))`;
              const tooltip = t("journal.heatmapTooltip", {
                winRate: (winRate * 100).toFixed(0),
                trades: cell.trades,
                wins: cell.wins,
                losses,
              });
              return (
                <Tooltip key={`${displayIdx}-${h}`}>
                  <TooltipTrigger asChild>
                    <div
                      className="rounded-sm flex items-center justify-center text-micro cursor-default"
                      style={{
                        aspectRatio: "1",
                        minHeight: 18,
                        backgroundColor: bg,
                      }}
                    >
                      {cell.trades}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="text-micro">
                    {tooltip}
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </Fragment>
        );
        })}
      </div>
    </div>
  );
}

export default function JournalStatsPanel({
  refreshKey = 0,
}: {
  refreshKey?: number;
}) {
  const { t, i18n } = useTranslation();
  const isZh = i18n.language.startsWith("zh");
  const weekdayLabels = isZh ? WEEKDAY_LABELS_ZH : WEEKDAY_LABELS_EN;
  const weekdayOrder = isZh ? WEEKDAY_ORDER_ZH : WEEKDAY_ORDER_EN;

  const [stats, setStats] = useState<TradeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState<RangePreset>("all");
  const [range, setRange] = useState<{ from: Date; to: Date } | null>(null);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [draft, setDraft] = useState<{ from: Date; to?: Date } | undefined>(
    undefined,
  );

  const [dimensionTab, setDimensionTab] = useState<DimensionTab>("symbol");

  const [kpiExpanded, setKpiExpanded] = useState(false);

  const handleKpiToggle = () => {
    setKpiExpanded((prev) => !prev);
  };

  const { startingCapital, setStartingCapital, displayMoney } = useJournalSettings();

  const handlePresetChange = (next: RangePreset) => {
    setPreset(next);
    if (next === "all") setRange(null);
    else if (next !== "custom") setRange(computePresetRange(next));
  };

  const handleCalendarOpenChange = (open: boolean) => {
    setCalendarOpen(open);
    if (open) {
      setDraft(range ? { from: range.from, to: range.to } : undefined);
    } else {
      setDraft(undefined);
    }
  };

  const handleRangeSelect = (r: { from?: Date; to?: Date } | undefined) => {
    if (!r?.from) {
      setDraft(undefined);
      return;
    }
    setDraft({ from: r.from, to: r.to });
    if (r.to) {
      setRange({ from: startOfDay(r.from), to: endOfDay(r.to) });
      setPreset("custom");
      setCalendarOpen(false);
      setDraft(undefined);
    }
  };

  // Fetch stats when the effective range or refreshKey changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = range
      ? { date_from: range.from.toISOString(), date_to: range.to.toISOString() }
      : undefined;
    fetchTradeStats(params)
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => { /* toast handled by client */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [range, refreshKey]);

  const dimensionData = useMemo((): GroupStats[] => {
    if (!stats) return [];
    if (dimensionTab === "symbol") return stats.by_symbol;
    if (dimensionTab === "direction") return stats.by_direction;
    return stats.by_tag;
  }, [stats, dimensionTab]);

  // ECharts option for dimension analysis — horizontal bar chart (PnL per dimension)
  const dimensionChartOption = useMemo(() => {
    if (!dimensionData.length) return null;
    const cs = getComputedStyle(document.documentElement);
    const textColor = cs.getPropertyValue("--text-secondary").trim();
    const borderColor = cs.getPropertyValue("--border").trim();
    const successColor = cs.getPropertyValue("--success").trim();
    const dangerColor = cs.getPropertyValue("--danger").trim();
    const primaryColor = cs.getPropertyValue("--text-primary").trim();
    const panelBg = cs.getPropertyValue("--panel-bg").trim() || "#1a1a1a";

    // Sort by PnL descending so the best performers are on top
    const sorted = [...dimensionData].sort((a, b) => b.total_pnl - a.total_pnl);
    const categories = sorted.map(dimensionKey);
    const values = sorted.map((r) => r.total_pnl);

    return {
      grid: { left: 8, right: 72, top: 8, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        backgroundColor: panelBg,
        borderColor,
        textStyle: { color: primaryColor, fontSize: 12 },
        formatter: (params: unknown) => {
          const p = (params as { dataIndex: number }[])[0];
          const row = sorted[p.dataIndex];
          return `<div style="font-weight:600;margin-bottom:4px">${dimensionKey(row)}</div>` +
            `${t("journal.pnl")}: ${displayMoney(row.total_pnl, { signed: true })}<br/>` +
            `${t("journal.count")}: ${row.count}<br/>` +
            `${t("journal.winRate")}: ${formatPct(row.win_rate)}`;
        },
      },
      xAxis: {
        type: "value" as const,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: textColor,
          fontSize: 10,
          formatter: (value: number) => displayMoney(value),
        },
        splitLine: { lineStyle: { color: borderColor, type: "dashed" as const } },
      },
      yAxis: {
        type: "category" as const,
        data: categories,
        axisLine: { lineStyle: { color: borderColor } },
        axisTick: { show: false },
        axisLabel: { color: textColor, fontSize: 11 },
      },
      series: [
        {
          type: "bar" as const,
          data: values.map((v) => ({
            value: v,
            itemStyle: { color: v >= 0 ? successColor : dangerColor, borderRadius: [0, 4, 4, 0] },
          })),
          label: {
            show: true,
            position: "right" as const,
            formatter: (params: { value: number }) => displayMoney(params.value, { signed: true }),
            color: textColor,
            fontSize: 10,
          },
          barMaxWidth: 20,
        },
      ],
    };
  }, [dimensionData, displayMoney, t]);

  const presetLabel = (p: RangePreset): string => {
    if (p === "custom") return t("journal.range.customRange");
    return t(`journal.range.${p}`);
  };

  const dimensionTabs: { value: DimensionTab; label: string }[] = [
    { value: "symbol", label: t("journal.bySymbol") },
    { value: "direction", label: t("journal.byDirection") },
    { value: "tag", label: t("journal.byTag") },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end gap-2 pt-4">
        <Select
          value={preset}
          onValueChange={(v) => handlePresetChange(v as RangePreset)}
        >
          <SelectTrigger
            size="sm"
            className="w-[144px]"
            style={{
              fontSize: journalStatsControlSizes.fontSize,
              fontWeight: journalStatsControlSizes.fontWeight,
            }}
          >
            <SelectValue>{presetLabel(preset)}</SelectValue>
          </SelectTrigger>
          <SelectContent align="end">
            {PRESET_ORDER.map((p) => (
              <SelectItem
                key={p}
                value={p}
                style={{
                  fontSize: journalStatsControlSizes.fontSize,
                  fontWeight: journalStatsControlSizes.fontWeight,
                }}
              >
                {presetLabel(p)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Popover open={calendarOpen} onOpenChange={handleCalendarOpenChange}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              style={{
                fontSize: journalStatsControlSizes.fontSize,
                fontWeight: journalStatsControlSizes.fontWeight,
              }}
            >
              <CalendarIcon className="size-[var(--icon-sm)]" />
              {range ? (
                formatRangeLabel(range.from, range.to)
              ) : (
                <span className="text-[var(--text-faint)]">
                  {t("journal.range.pickDates")}
                </span>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
            <Calendar
              mode="range"
              selected={draft}
              onSelect={handleRangeSelect}
              resetOnSelect
              numberOfMonths={2}
              defaultMonth={draft?.from ?? range?.from}
            />
          </PopoverContent>
        </Popover>
        <StartingCapitalButton
          startingCapital={startingCapital}
          onChange={setStartingCapital}
        />
      </div>

      {loading && !stats ? (
        <div className="analysis-state" style={{ padding: "40px 0" }}>
          <div className="spinner" />
        </div>
      ) : !stats || stats.total_trades === 0 ? (
        <Empty className="min-h-[220px] border border-dashed border-border bg-[var(--chip-bg)]">
          <EmptyHeader>
            <EmptyTitle className="text-subheading text-foreground">
              {t("journal.noData")}
            </EmptyTitle>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          <KpiRow stats={stats} expanded={kpiExpanded} onToggle={handleKpiToggle} />
          <KpiDetailPanel stats={stats} expanded={kpiExpanded} />

          {startingCapital != null && (
            <EquityCurveChart stats={stats} startingCapital={startingCapital} />
          )}

          <PnlHistoryChart stats={stats} />
          <DistributionChart stats={stats} />
          <CompositionCharts stats={stats} />
        </>
      )}

      <JournalTradingCalendarCard />

      {!loading && stats && stats.total_trades > 0 && (
        <Card>
          <CardHeader className="pb-0">
            <CardTitle>{t("journal.dimensionAnalysis")}</CardTitle>
            <CardAction>
              <ToggleGroup
                type="single"
                variant="outline"
                size={journalStatsControlSizes.dimensionToggle}
                value={dimensionTab}
                onValueChange={(val) => { if (val) setDimensionTab(val as DimensionTab); }}
                spacing={1}
              >
                {dimensionTabs.map((tab) => (
                  <ToggleGroupItem
                    key={tab.value}
                    value={tab.value}
                    style={{
                      fontSize: journalStatsControlSizes.fontSize,
                      fontWeight: journalStatsControlSizes.fontWeight,
                    }}
                  >
                    {tab.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </CardAction>
          </CardHeader>
          <CardContent>
            {!dimensionChartOption ? (
              <div className="text-ui text-muted-foreground py-3">
                {t("journal.noData")}
              </div>
            ) : (
              <ReactECharts
                option={dimensionChartOption}
                style={{ height: Math.max(160, dimensionData.length * 32 + 32) }}
                opts={{ renderer: "svg" }}
                notMerge
              />
            )}
          </CardContent>
        </Card>
      )}

      {stats && stats.by_hour_weekday && stats.by_hour_weekday.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-subheading">{t("journal.heatmap")}</CardTitle>
          </CardHeader>
          <CardContent>
            <HeatmapGrid data={stats.by_hour_weekday} t={t} weekdayLabels={weekdayLabels} weekdayOrder={weekdayOrder} />
          </CardContent>
        </Card>
      )}

    </div>
  );
}
