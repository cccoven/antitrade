import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, TrendingUp, TrendingDown } from "lucide-react";
import { format, startOfMonth } from "date-fns";
import { enUS, zhCN } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar, CalendarDayButton } from "@/components/ui/calendar";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  fetchTradeCalendarSummary,
  type JournalCalendarDaySummary,
  type JournalCalendarSummary,
} from "@/api/client";
import {
  buildJournalCalendarYearOptions,
  setJournalCalendarMonth,
  toJournalMonthKey,
} from "@/pages/journal-calendar";
import { journalCalendarControlSizes } from "@/pages/journal-ui-config";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface MonthMetrics {
  totalPnl: number;
  totalTrades: number;
  winRate: number;
  activeDays: number;
}

function computeMonthMetrics(
  data: JournalCalendarSummary | null
): MonthMetrics | null {
  if (!data) return null;
  const days = data.days.filter((d) => d.trade_count > 0);
  const totalPnl = days.reduce((s, d) => s + d.total_pnl, 0);
  const totalTrades = days.reduce((s, d) => s + d.trade_count, 0);
  const wins = days.reduce(
    (s, d) => s + Math.round(d.trade_count * d.win_rate),
    0
  );
  const winRate = totalTrades > 0 ? wins / totalTrades : 0;
  const activeDays = days.length;
  return { totalPnl, totalTrades, winRate, activeDays };
}

function prevMonthKey(key: string): string {
  const [yearStr, monthStr] = key.split("-");
  let year = Number(yearStr);
  let mo = Number(monthStr) - 1; // 1-based to 0-based
  if (mo === 0) {
    year -= 1;
    mo = 12;
  }
  return `${year}-${String(mo).padStart(2, "0")}`;
}

function MonthlySummaryItem({
  label,
  value,
  valueColor,
  delta,
  improved,
}: {
  label: string;
  value: string;
  valueColor?: string;
  delta: string | null;
  improved: boolean;
}) {
  return (
    <div className="flex-1 min-w-[100px] rounded-[12px] border border-border bg-[color-mix(in_srgb,var(--chip-bg)_62%,transparent)] px-3 py-2.5 space-y-1.5">
      <div className="text-caption text-muted-foreground">{label}</div>
      <div
        className="text-heading font-medium"
        style={valueColor ? { color: valueColor } : undefined}
      >
        {value}
      </div>
      {delta && (
        <div
          className="flex items-center gap-0.5 text-caption"
          style={{ color: improved ? "var(--success)" : "var(--danger)" }}
        >
          {improved
            ? <TrendingUp className="size-[var(--icon-xs)]" />
            : <TrendingDown className="size-[var(--icon-xs)]" />}
          {delta}
        </div>
      )}
    </div>
  );
}

function TradingCalendarDayButton({
  day,
  modifiers,
  summary,
}: React.ComponentProps<typeof CalendarDayButton> & {
  summary?: JournalCalendarDaySummary;
}) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();
  const hasTrades = !!summary && summary.trade_count > 0;
  const isPositive = (summary?.total_pnl ?? 0) > 0;
  const isNegative = (summary?.total_pnl ?? 0) < 0;

  return (
    <CalendarDayButton
      day={day}
      modifiers={modifiers}
      className={cn(
        "!pointer-events-none !relative !aspect-square !h-auto !w-full !cursor-default !overflow-hidden !rounded-[12px] border border-border px-2 py-2 text-left transition-colors",
        journalCalendarControlSizes.dayCellHeightClassName,
        hasTrades
          ? "bg-[var(--chip-bg)]"
          : "bg-[color-mix(in_srgb,var(--chip-bg)_56%,transparent)] text-muted-foreground",
        isPositive && journalCalendarControlSizes.dayPositiveToneClassName,
        isNegative && journalCalendarControlSizes.dayNegativeToneClassName
      )}
    >
      <div className="absolute right-3 top-2 flex items-start justify-end">
        <span className="text-caption text-muted-foreground">{day.date.getDate()}</span>
      </div>
      {hasTrades ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5 px-2 text-center">
          <span
            className={cn(
              "font-semibold",
              journalCalendarControlSizes.dayValueTextClassName,
              isPositive && "text-[var(--success)] dark:text-white",
              isNegative && "text-[var(--danger)] dark:text-white",
              !isPositive && !isNegative && "text-foreground"
            )}
          >
            {displayMoney(summary.total_pnl, { signed: true })}
          </span>
          <span className="text-caption text-muted-foreground">
            {t("journal.calendarTrades", { count: summary.trade_count })}
          </span>
        </div>
      ) : (
        <div className="h-full w-full" />
      )}
    </CalendarDayButton>
  );
}

export default function JournalTradingCalendarCard() {
  const { t, i18n } = useTranslation();
  const { amountsVisible, displayMoney } = useJournalSettings();
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const [monthPickerOpen, setMonthPickerOpen] = useState(false);
  const [summary, setSummary] = useState<Awaited<
    ReturnType<typeof fetchTradeCalendarSummary>
  > | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const monthKey = toJournalMonthKey(month);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTradeCalendarSummary(monthKey)
      .then((data) => {
        if (!cancelled) {
          setSummary(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(t("error.generic"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [monthKey, t]);

  const [prevSummary, setPrevSummary] = useState<JournalCalendarSummary | null>(
    null
  );
  const prevKey = useMemo(() => prevMonthKey(monthKey), [monthKey]);

  useEffect(() => {
    let cancelled = false;
    setPrevSummary(null);
    fetchTradeCalendarSummary(prevKey)
      .then((data) => {
        if (!cancelled) setPrevSummary(data);
      })
      .catch(() => {
        /* prev month comparison is optional */
      });
    return () => {
      cancelled = true;
    };
  }, [prevKey]);

  const currentMetrics = useMemo(
    () => computeMonthMetrics(summary),
    [summary]
  );
  const prevMetrics = useMemo(
    () => computeMonthMetrics(prevSummary),
    [prevSummary]
  );

  const formatDelta = useCallback(
    (
      curr: number,
      prev: number | undefined,
      mode: "abs" | "pct" = "abs"
    ): { delta: string | null; improved: boolean } => {
      if (prev === undefined)
        return { delta: null, improved: false };
      if (mode === "pct") {
        const diff = curr - prev;
        const sign = diff > 0 ? "+" : "";
        return {
          delta: `${sign}${(diff * 100).toFixed(0)}%`,
          improved: diff > 0,
        };
      }
      const diff = curr - prev;
      const sign = diff > 0 ? "+" : "";
      return {
        delta: `${sign}${Number.isInteger(diff) ? diff : diff.toFixed(1)}`,
        improved: diff > 0,
      };
    },
    []
  );

  const locale = i18n.language.startsWith("zh") ? zhCN : enUS;
  const monthOptions = useMemo(
    () =>
      Array.from({ length: 12 }, (_, monthIndex) => ({
        value: monthIndex,
        label: i18n.language.startsWith("zh")
          ? format(new Date(month.getFullYear(), monthIndex, 1), "M月")
          : format(new Date(month.getFullYear(), monthIndex, 1), "MMM", {
              locale,
            }),
      })),
    [i18n.language, locale, month]
  );
  const yearOptions = useMemo(
    () => buildJournalCalendarYearOptions(month),
    [month]
  );
  const daySummaryMap = useMemo(() => {
    return new Map((summary?.days ?? []).map((entry) => [entry.date, entry]));
  }, [summary]);

  const monthLabel = i18n.language.startsWith("zh")
    ? format(month, "yyyy年M月")
    : format(month, "MMMM yyyy", { locale });
  const activeYear = String(month.getFullYear());

  const handleYearChange = (value: string) => {
    setMonth((current) =>
      setJournalCalendarMonth(current, Number(value), current.getMonth())
    );
  };

  const handleMonthPick = (monthIndex: number) => {
    setMonth((current) =>
      setJournalCalendarMonth(current, current.getFullYear(), monthIndex)
    );
    setMonthPickerOpen(false);
  };
  const isInitialLoading = loading && summary === null;
  const isRefreshing = loading && summary !== null;

  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle>{t("journal.tradingCalendar")}</CardTitle>
        <CardAction>
          <Popover open={monthPickerOpen} onOpenChange={setMonthPickerOpen}>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size={journalCalendarControlSizes.monthPickerAction}
                className="min-w-[148px] justify-between"
                style={{
                  fontSize: journalCalendarControlSizes.monthPickerFontSize,
                  fontWeight: journalCalendarControlSizes.monthPickerFontWeight,
                }}
                aria-label={t("journal.selectMonth")}
              >
                <span>{monthLabel}</span>
                <ChevronDown className="size-4 text-muted-foreground" />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              align="end"
              sideOffset={6}
              className={cn(
                "grid gap-3 p-3",
                journalCalendarControlSizes.monthPickerContentWidthClassName
              )}
            >
              <div className="grid gap-1.5">
                <span
                  className={cn(
                    "font-medium text-muted-foreground",
                    journalCalendarControlSizes.monthPickerMetaTextClassName
                  )}
                >
                  {t("journal.year")}
                </span>
                <Select value={activeYear} onValueChange={handleYearChange}>
                  <SelectTrigger
                    size="sm"
                    className="w-full"
                    style={{
                      fontSize: "var(--font-caption)",
                      fontWeight: 400,
                    }}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="end">
                    {yearOptions.map((year) => (
                      <SelectItem
                        key={year}
                        value={String(year)}
                        style={{
                          fontSize: "var(--font-caption)",
                          fontWeight: 400,
                        }}
                      >
                        {year}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-1.5">
                <span
                  className={cn(
                    "font-medium text-muted-foreground",
                    journalCalendarControlSizes.monthPickerMetaTextClassName
                  )}
                >
                  {t("journal.month")}
                </span>
                <div className={journalCalendarControlSizes.monthPickerGridClassName}>
                  {monthOptions.map((option) => (
                    <Button
                      key={option.value}
                      type="button"
                      variant={option.value === month.getMonth() ? "secondary" : "outline"}
                      size="sm"
                      className="justify-center"
                      style={{
                        fontSize: journalCalendarControlSizes.monthPickerFontSize,
                        fontWeight: journalCalendarControlSizes.monthPickerFontWeight,
                      }}
                      onClick={() => handleMonthPick(option.value)}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
              </div>
            </PopoverContent>
          </Popover>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isInitialLoading ? (
          <div className="analysis-state py-8">
            <div className="spinner" />
          </div>
        ) : error && summary === null ? (
          <div className="text-ui text-destructive py-2">{error}</div>
        ) : (
          <>
            {currentMetrics && currentMetrics.totalTrades > 0 && (
              <div className="flex gap-3 flex-wrap mb-3">
                <MonthlySummaryItem
                  label={t("journal.totalPnl")}
                  value={displayMoney(currentMetrics.totalPnl, { signed: true })}
                  valueColor={
                    currentMetrics.totalPnl > 0
                      ? "var(--success)"
                      : currentMetrics.totalPnl < 0
                        ? "var(--danger)"
                        : undefined
                  }
                  {...(
                    amountsVisible
                      ? formatDelta(currentMetrics.totalPnl, prevMetrics?.totalPnl)
                      : { delta: null, improved: false }
                  )}
                />
                <MonthlySummaryItem
                  label={t("journal.winRate")}
                  value={`${(currentMetrics.winRate * 100).toFixed(0)}%`}
                  {...formatDelta(
                    currentMetrics.winRate,
                    prevMetrics?.winRate,
                    "pct"
                  )}
                />
                <MonthlySummaryItem
                  label={t("journal.tradeCount")}
                  value={String(currentMetrics.totalTrades)}
                  {...formatDelta(
                    currentMetrics.totalTrades,
                    prevMetrics?.totalTrades
                  )}
                />
                <MonthlySummaryItem
                  label={t("journal.activeDays")}
                  value={String(currentMetrics.activeDays)}
                  {...formatDelta(
                    currentMetrics.activeDays,
                    prevMetrics?.activeDays
                  )}
                />
              </div>
            )}
            <div
              className={cn(
                "grid gap-4 transition-opacity lg:grid-cols-[minmax(0,7fr)_minmax(240px,3fr)]",
                isRefreshing && "opacity-80"
              )}
              aria-busy={isRefreshing}
            >
            <div className="rounded-[16px] border border-border bg-[color-mix(in_srgb,var(--chip-bg)_62%,transparent)] p-3">
              <Calendar
                onDayClick={() => {}}
                month={month}
                locale={locale}
                showOutsideDays={false}
                fixedWeeks
                className="w-full p-0"
                classNames={{
                  root: "w-full",
                  months: "w-full",
                  month: "w-full gap-2",
                  month_grid: cn(
                    "w-full table-fixed border-separate",
                    journalCalendarControlSizes.dayGridSpacingClassName
                  ),
                  month_caption: "hidden",
                  nav: "hidden",
                  weekdays: "border-b border-border",
                  weekday:
                    "py-1 text-center text-[length:var(--font-caption)] font-medium text-muted-foreground",
                  week: "",
                  day: "p-0 align-top",
                  today: "text-foreground",
                }}
                components={{
                  DayButton: (props) => {
                    const dayKey = format(props.day.date, "yyyy-MM-dd");
                    const daySummary = daySummaryMap.get(dayKey);
                    return (
                      <TradingCalendarDayButton
                        {...props}
                        summary={daySummary}
                      />
                    );
                  },
                }}
              />
            </div>

            <div className="grid gap-3">
              {(summary?.weeks ?? []).length > 0 ? (
                (summary?.weeks ?? []).map((week) => (
                  <Card
                    key={week.week_index}
                    className="gap-2 rounded-[16px] border-border bg-[color-mix(in_srgb,var(--chip-bg)_62%,transparent)] py-4 shadow-none"
                  >
                    <CardContent className="grid content-center gap-1 px-4">
                      <div>
                        <span
                          className={cn(
                            "font-medium text-muted-foreground",
                            journalCalendarControlSizes.weekTitleTextClassName
                          )}
                        >
                          {t("journal.weekLabel", { index: week.week_index })}
                        </span>
                      </div>
                      <div>
                        <span
                          className={cn(
                            "font-semibold",
                            journalCalendarControlSizes.weekValueTextClassName,
                            week.total_pnl > 0 && "text-[var(--success)]",
                            week.total_pnl < 0 && "text-[var(--danger)]"
                          )}
                        >
                          {displayMoney(week.total_pnl, { signed: true })}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        <Badge
                          variant="outline"
                          className={cn(
                            "rounded-md",
                            journalCalendarControlSizes.weekMetaBadgeSurfaceClassName,
                            journalCalendarControlSizes.weekMetaTextClassName
                          )}
                        >
                          {t("journal.calendarActiveDays", { count: week.active_days })}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={cn(
                            "rounded-md",
                            journalCalendarControlSizes.weekMetaBadgeSurfaceClassName,
                            journalCalendarControlSizes.weekMetaTextClassName
                          )}
                        >
                          {t("journal.calendarTrades", { count: week.trade_count })}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Card className="rounded-[16px] border-border bg-[color-mix(in_srgb,var(--chip-bg)_62%,transparent)] py-4 shadow-none">
                  <CardContent className="px-4 py-3 text-ui text-muted-foreground">
                    {error ?? t("journal.noData")}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
