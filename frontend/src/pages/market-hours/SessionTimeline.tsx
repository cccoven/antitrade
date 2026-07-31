import type { MarketHoursGroup, MarketHoursItem, MarketHoursSession } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { sessionTone } from "../market-hours-ui-config";
import {
  countryMarker,
  localized,
  nowPosition,
  timelineStyle,
  visibleSessionLabel,
} from "./market-hours-utils";

const timelineGridClass = "grid min-w-[934px] grid-cols-[156px_720px_58px] md:min-w-[1000px] md:grid-cols-[220px_minmax(720px,1fr)_76px]";
const hourTicks = Array.from({ length: 8 }, (_, index) => index * 3);

function StateBadge({ state, t }: { state: MarketHoursItem["state"]; t: (key: string) => string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "px-1.5 text-micro",
        state === "closed" && "text-muted-foreground",
        state === "main" && "border-emerald-500/35 bg-emerald-500/10 text-emerald-500",
        state === "night" && "border-violet-500/35 bg-violet-500/10 text-violet-500",
        state === "pre" && "border-sky-500/35 bg-sky-500/10 text-sky-500",
        state === "after" && "border-amber-500/35 bg-amber-500/10 text-amber-500",
      )}
    >
      {t(`marketHours.state.${state}`)}
    </Badge>
  );
}

export function TimelineAxis() {
  return (
    <div className={cn(timelineGridClass, "h-9 border-b border-border/50 bg-muted/15")}>
      <div className="sticky left-0 z-[3] border-r border-border/50 bg-card" />
      <div className="relative">
        {hourTicks.map((hour) => (
          <span
            key={hour}
            className={cn(
              "absolute top-1/2 -translate-y-1/2 text-micro tabular-nums text-muted-foreground",
              hour > 0 && "-translate-x-1/2",
            )}
            style={{ left: `${(hour / 24) * 100}%` }}
          >
            {String(hour).padStart(2, "0")}
          </span>
        ))}
      </div>
      <div className="sticky right-0 z-[3] border-l border-border/50 bg-card" />
    </div>
  );
}

export function TimelineTrack({
  sessions,
  now,
  windowStartAt,
  windowEndAt,
  referenceTimezone,
  locale,
}: {
  sessions: MarketHoursSession[];
  now: Date;
  windowStartAt: string;
  windowEndAt: string;
  referenceTimezone: string;
  locale: string;
}) {
  const currentPosition = nowPosition(now, windowStartAt, windowEndAt);
  return (
    <div
      className="relative h-7 w-full overflow-hidden rounded-[5px] border border-border/35 bg-muted/35"
      style={{
        backgroundImage: "linear-gradient(to right, transparent calc(100% - 1px), var(--border) 100%)",
        backgroundSize: "calc(100% / 24) 100%",
      }}
    >
      {sessions.map((session, index) => {
        const style = timelineStyle(session.start_at, session.end_at, windowStartAt, windowEndAt);
        if (!style) return null;
        return (
          <span
            key={`${session.start_at}-${session.end_at}-${index}`}
            className={cn("absolute inset-y-[3px] rounded-[3px] border", sessionTone[session.kind])}
            style={style}
            title={visibleSessionLabel(session, referenceTimezone, locale)}
          />
        );
      })}
      <span
        className="pointer-events-none absolute inset-y-0 z-[2] w-px bg-primary shadow-[0_0_8px_color-mix(in_srgb,var(--primary)_60%,transparent)]"
        style={{ left: `${currentPosition}%` }}
      />
    </div>
  );
}

function MarketRow({
  item,
  now,
  language,
  locale,
  referenceTimezone,
  windowStartAt,
  windowEndAt,
  onSelect,
  t,
}: {
  item: MarketHoursItem;
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
    <button
      type="button"
      className={cn(timelineGridClass, "group border-b border-border/30 text-left last:border-b-0")}
      style={{ fontSize: "var(--font-ui)" }}
      onClick={() => onSelect(item)}
      aria-label={localized(item.name, language)}
    >
      <span className="sticky left-0 z-[2] flex min-w-0 items-center gap-2 border-r border-border/40 bg-card px-3 py-1.5 transition-colors group-hover:bg-muted">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-caption">
          {countryMarker[item.country_code] ?? item.country_code}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-ui font-medium text-foreground">{localized(item.name, language)}</span>
          <span className="block truncate text-micro text-muted-foreground">{localized(item.city, language)}</span>
        </span>
      </span>
      <span className="flex items-center px-2 py-1.5 transition-colors group-hover:bg-muted/40">
        <TimelineTrack
          sessions={item.sessions}
          now={now}
          windowStartAt={windowStartAt}
          windowEndAt={windowEndAt}
          referenceTimezone={referenceTimezone}
          locale={locale}
        />
      </span>
      <span className="sticky right-0 z-[2] flex items-center justify-center border-l border-border/40 bg-card px-1 transition-colors group-hover:bg-muted">
        <StateBadge state={item.state} t={t} />
      </span>
    </button>
  );
}

export default function SessionTimeline({
  groups,
  now,
  language,
  locale,
  referenceTimezone,
  windowStartAt,
  windowEndAt,
  onSelect,
  t,
}: {
  groups: Array<{ group: MarketHoursGroup; items: MarketHoursItem[] }>;
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
      <div className="overflow-x-auto">
        <TimelineAxis />
        {groups.map(({ group, items }) => (
          <div key={group}>
            <div className={cn(timelineGridClass, "border-b border-border/40 bg-muted/20")}>
              <div className="sticky left-0 z-[2] border-r border-border/40 bg-muted px-3 py-2 text-caption font-semibold uppercase tracking-wide text-muted-foreground">
                {t(`marketHours.groupTitle.${group}`)}
              </div>
              <div />
              <div className="sticky right-0 z-[2] border-l border-border/40 bg-muted" />
            </div>
            {items.map((item) => (
              <MarketRow
                key={item.id}
                item={item}
                now={now}
                language={language}
                locale={locale}
                referenceTimezone={referenceTimezone}
                windowStartAt={windowStartAt}
                windowEndAt={windowEndAt}
                onSelect={onSelect}
                t={t}
              />
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}
