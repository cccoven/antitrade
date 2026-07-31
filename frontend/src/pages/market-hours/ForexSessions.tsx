import type { MarketHoursItem, MarketHoursOverlap } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { TimelineAxis, TimelineTrack } from "./SessionTimeline";
import { countryMarker, formatSessionTime, localized } from "./market-hours-utils";

const rowClass = "grid min-w-[934px] grid-cols-[156px_720px_58px] md:min-w-[1000px] md:grid-cols-[220px_minmax(720px,1fr)_76px]";

export default function ForexSessions({
  items,
  overlaps,
  now,
  language,
  locale,
  referenceTimezone,
  windowStartAt,
  windowEndAt,
  onSelect,
  t,
}: {
  items: MarketHoursItem[];
  overlaps: MarketHoursOverlap[];
  now: Date;
  language: string;
  locale: string;
  referenceTimezone: string;
  windowStartAt: string;
  windowEndAt: string;
  onSelect: (item: MarketHoursItem) => void;
  t: (key: string) => string;
}) {
  return (
    <Card className="gap-0 overflow-hidden rounded-[10px] bg-[var(--panel-card-bg)] py-0">
      <CardHeader className="border-b border-border/50 px-4 py-3">
        <CardTitle>{t("marketHours.forexTitle")}</CardTitle>
        <div className="text-caption text-muted-foreground">{t("marketHours.forexSubtitle")}</div>
      </CardHeader>
      <div className="overflow-x-auto">
        <TimelineAxis />
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={cn(rowClass, "group border-b border-border/30 text-left last:border-b-0")}
            style={{ fontSize: "var(--font-ui)" }}
            onClick={() => onSelect(item)}
          >
            <span className="sticky left-0 z-[2] flex items-center gap-2 border-r border-border/40 bg-card px-3 py-1.5 group-hover:bg-muted">
              <span className="flex size-6 items-center justify-center rounded-md bg-muted text-caption">
                {countryMarker[item.country_code] ?? item.country_code}
              </span>
              <span className="truncate text-ui font-medium">{localized(item.name, language)}</span>
            </span>
            <span className="flex items-center px-2 py-1.5 group-hover:bg-muted/40">
              <TimelineTrack
                sessions={item.sessions}
                now={now}
                windowStartAt={windowStartAt}
                windowEndAt={windowEndAt}
                referenceTimezone={referenceTimezone}
                locale={locale}
              />
            </span>
            <span className="sticky right-0 z-[2] flex items-center justify-center border-l border-border/40 bg-card group-hover:bg-muted">
              <Badge
                variant="outline"
                className={cn(
                  "px-1.5 text-micro",
                  item.state === "closed" ? "text-muted-foreground" : "border-emerald-500/35 bg-emerald-500/10 text-emerald-500",
                )}
              >
                {t(`marketHours.state.${item.state}`)}
              </Badge>
            </span>
          </button>
        ))}
      </div>
      <CardContent className="grid gap-2 border-t border-border/50 px-4 py-3 md:grid-cols-2">
        {overlaps.map((overlap) => (
          <div key={overlap.id} className="rounded-md border border-border bg-muted/25 px-3 py-2">
            <div className="text-caption font-medium text-foreground">{t(`marketHours.overlap.${overlap.id}`)}</div>
            <div className="mt-1 text-micro text-muted-foreground">
              {overlap.sessions.length
                ? overlap.sessions.map((session) => `${formatSessionTime(session.start_at, referenceTimezone, locale)}–${formatSessionTime(session.end_at, referenceTimezone, locale)}`).join(", ")
                : t("marketHours.overlap.none")}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
