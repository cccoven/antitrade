import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { MarketOverviewCalendarEvent } from "@/api/client";

const buttonStyle = { fontSize: "var(--font-ui)" };

export function localDateKey(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function dateFromKey(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function eventValue(value: string | null) {
  return value?.trim() || "—";
}

export default function EconomicCalendar({
  items,
  sourceUrl,
  language,
  selectedDate,
  onSelectedDateChange,
  unavailable,
}: {
  items: MarketOverviewCalendarEvent[];
  sourceUrl?: string;
  language: string;
  selectedDate: string;
  onSelectedDateChange: (value: string) => void;
  unavailable: boolean;
}) {
  const { t } = useTranslation();
  const [datePickerOpen, setDatePickerOpen] = useState(false);
  const locale = language === "zh" ? "zh-CN" : "en-US";
  const timeFormatter = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" });
  const selected = dateFromKey(selectedDate);
  const today = new Date();
  const todayKey = localDateKey(today);
  const selectedItems = items.filter((item) => localDateKey(new Date(item.date)) === selectedDate);
  const anchor = items.length ? new Date(items[0].date) : today;
  const weekStart = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() - anchor.getDay());
  const weekEnd = new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + 6, 23, 59, 59);
  const selectedLabel = new Intl.DateTimeFormat(locale, {
    weekday: "short", year: "numeric", month: "short", day: "numeric",
  }).format(selected);

  return (
    <Card className="gap-0 overflow-hidden rounded-[var(--radius-data-panel)] border-[var(--data-grid-line)] bg-[var(--data-panel-bg)] py-0 shadow-none">
      <CardHeader className="flex min-h-11 flex-row flex-wrap items-center justify-between gap-2 border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] px-3 py-2">
        <div className="flex items-center gap-2">
          <CalendarDays className="size-[var(--icon-sm)] text-[var(--market-info)]" />
          <CardTitle className="text-micro uppercase tracking-[0.12em] text-muted-foreground">{t("marketOverview.calendar")}</CardTitle>
          <span className="text-micro text-muted-foreground">{t("marketOverview.calendarLocalTime")}</span>
        </div>
        <div className="flex items-center gap-2">
          <Popover open={datePickerOpen} onOpenChange={setDatePickerOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" style={buttonStyle} className="min-w-40 justify-start font-normal">
                <CalendarDays />{selectedLabel}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="end">
              <Calendar
                mode="single"
                selected={selected}
                defaultMonth={selected}
                disabled={{ before: weekStart, after: weekEnd }}
                onSelect={(date) => {
                  if (!date) return;
                  onSelectedDateChange(localDateKey(date));
                  setDatePickerOpen(false);
                }}
              />
            </PopoverContent>
          </Popover>
          <Button variant="outline" size="sm" style={buttonStyle} onClick={() => onSelectedDateChange(todayKey)} disabled={selectedDate === todayKey}>
            {t("marketOverview.calendarToday")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="px-0">
        {unavailable ? (
          <div className="px-4 py-10 text-center text-ui text-muted-foreground">{t("marketOverview.error.calendar_unavailable")}</div>
        ) : selectedItems.length === 0 ? (
          <div className="px-4 py-10 text-center text-ui text-muted-foreground">{t("marketOverview.calendarEmpty")}</div>
        ) : (
          <Table>
            <TableHeader className="bg-[var(--data-panel-header-bg)] [&_tr]:border-[var(--data-grid-line)]">
              <TableRow className="hover:bg-transparent">
                <TableHead className="h-8 px-4 text-caption text-muted-foreground">{t("marketOverview.calendarTime")}</TableHead>
                <TableHead className="h-8 text-caption text-muted-foreground">{t("marketOverview.calendarCurrency")}</TableHead>
                <TableHead className="h-8 text-caption text-muted-foreground">{t("marketOverview.calendarEvent")}</TableHead>
                <TableHead className="h-8 text-caption text-muted-foreground">{t("marketOverview.calendarImpact")}</TableHead>
                <TableHead className="h-8 text-right text-caption text-muted-foreground">{t("marketOverview.calendarActual")}</TableHead>
                <TableHead className="h-8 text-right text-caption text-muted-foreground">{t("marketOverview.calendarForecast")}</TableHead>
                <TableHead className="h-8 pr-4 text-right text-caption text-muted-foreground">{t("marketOverview.calendarPrevious")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {selectedItems.map((item) => (
                <TableRow key={`${item.date}-${item.currency}-${item.title}`} className="border-b border-[var(--data-grid-line)] hover:bg-muted/25">
                  <TableCell className="market-data-value px-4 text-caption text-[var(--market-info)]">{timeFormatter.format(new Date(item.date))}</TableCell>
                  <TableCell className="market-data-value font-semibold">{item.currency || "—"}</TableCell>
                  <TableCell className="min-w-48 whitespace-normal font-medium">{item.title || "—"}</TableCell>
                  <TableCell><span className={cn("inline-flex rounded-[4px] px-2 py-0.5 text-micro font-normal", item.impact === "high" ? "bg-red-500/10 text-[var(--market-down)]" : "bg-amber-500/10 text-[var(--market-warning)]")}>{t(`marketOverview.calendarImpact.${item.impact}`)}</span></TableCell>
                  <TableCell className="market-data-value text-right">{eventValue(item.actual)}</TableCell>
                  <TableCell className="market-data-value text-right text-muted-foreground">{eventValue(item.forecast)}</TableCell>
                  <TableCell className="market-data-value pr-4 text-right text-muted-foreground">{eventValue(item.previous)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {sourceUrl ? <div className="border-t border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] px-4 py-2 text-micro text-muted-foreground">{t("marketOverview.calendarSource")} <a className="hover:text-foreground" href={sourceUrl} target="_blank" rel="noreferrer">Forex Factory</a></div> : null}
      </CardContent>
    </Card>
  );
}
