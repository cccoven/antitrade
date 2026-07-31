import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  fetchMarketHours,
  listNotificationChannels,
  listNotificationSubscriptions,
  upsertNotificationSubscription,
  type MarketHours,
  type MarketHoursGroup,
  type NotificationChannel,
  type NotificationSubscription,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { showToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useI18n } from "@/i18n/i18n-context";
import { cn } from "@/lib/utils";
import {
  groupOrder,
  marketGroups,
  marketHoursControlSizes,
  referenceZones,
  sessionTone,
} from "./market-hours-ui-config";
import ForexSessions from "./market-hours/ForexSessions";
import MarketDetails from "./market-hours/MarketDetails";
import SessionTimeline from "./market-hours/SessionTimeline";
import {
  formatClock,
  formatDate,
  formatOffset,
  localized,
  marketStateAt,
} from "./market-hours/market-hours-utils";

function defaultTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai";
}

export default function MarketHoursTool() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { resolvedLanguage } = useI18n();
  const { user, setLoginDialogOpen } = useAuth();
  const locale = resolvedLanguage === "zh" ? "zh-CN" : "en-US";
  const [referenceTimezone, setReferenceTimezone] = useState(defaultTimezone);
  const [data, setData] = useState<MarketHours | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [groupFilter, setGroupFilter] = useState<"all" | MarketHoursGroup>("all");
  const [openOnly, setOpenOnly] = useState(false);
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null);
  const [notificationChannels, setNotificationChannels] = useState<NotificationChannel[]>([]);
  const [notificationSubscriptions, setNotificationSubscriptions] = useState<NotificationSubscription[]>([]);
  const [notificationBusy, setNotificationBusy] = useState(false);

  const load = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
      setError(false);
    }
    try {
      setData(await fetchMarketHours(referenceTimezone, background));
    } catch {
      if (!background) setError(true);
    } finally {
      if (!background) setLoading(false);
    }
  }, [referenceTimezone]);

  const loadNotifications = useCallback(async () => {
    if (!user) {
      setNotificationChannels([]);
      setNotificationSubscriptions([]);
      return;
    }
    try {
      const [channels, subscriptions] = await Promise.all([
        listNotificationChannels(),
        listNotificationSubscriptions(),
      ]);
      setNotificationChannels(channels);
      setNotificationSubscriptions(subscriptions);
    } catch {
      // API helper already shows a localized error.
    }
  }, [user]);

  useEffect(() => { void load(false); }, [load]);
  useEffect(() => { void loadNotifications(); }, [loadNotifications]);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!data) return;
    const currentTime = Date.now();
    const transitions = [...data.markets, ...data.forex_sessions]
      .map((item) => item.next_transition_at ? new Date(item.next_transition_at).getTime() : 0)
      .filter((value) => value > currentTime);
    const nextTransition = transitions.length ? Math.min(...transitions) : currentTime + 60_000;
    const delay = Math.min(60_000, Math.max(1_000, nextTransition - currentTime + 250));
    const timer = window.setTimeout(() => { void load(true); }, delay);
    return () => window.clearTimeout(timer);
  }, [data, load]);
  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void load(true);
    };
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => document.removeEventListener("visibilitychange", refreshWhenVisible);
  }, [load]);

  const liveMarkets = useMemo(() => (
    data?.markets.map((item) => ({ ...item, state: marketStateAt(item, now) })) ?? []
  ), [data, now]);
  const liveForexSessions = useMemo(() => (
    data?.forex_sessions.map((item) => ({ ...item, state: marketStateAt(item, now) })) ?? []
  ), [data, now]);

  const filteredGroups = useMemo(() => {
    const filtered = liveMarkets.filter((item) =>
      (groupFilter === "all" || item.group === groupFilter)
      && (!openOnly || item.state !== "closed"),
    );
    return groupOrder
      .map((group) => ({ group, items: filtered.filter((item) => item.group === group) }))
      .filter((entry) => entry.items.length);
  }, [liveMarkets, groupFilter, openOnly]);
  const selectedMarket = useMemo(() => (
    [...liveMarkets, ...liveForexSessions].find((item) => item.id === selectedMarketId) ?? null
  ), [liveForexSessions, liveMarkets, selectedMarketId]);
  const activeCount = liveMarkets.filter((item) => item.state !== "closed").length;
  const activeNotificationChannels = notificationChannels.filter((channel) => channel.status === "active");
  const selectedSubscriptions = selectedMarket
    ? notificationSubscriptions.filter((subscription) => (
      activeNotificationChannels.some((channel) => channel.id === subscription.channel_id)
      && subscription.event_type === "market.session.main_opened"
      && subscription.subject_type === "market"
      && subscription.subject_id === selectedMarket.id
    ))
    : [];
  const notificationEnabled = selectedSubscriptions.some((subscription) => subscription.enabled);

  const toggleOpeningNotification = async () => {
    if (!selectedMarket) return;
    if (!user) {
      setLoginDialogOpen(true);
      return;
    }
    if (!activeNotificationChannels.length) {
      navigate("/settings?section=notifications");
      return;
    }
    setNotificationBusy(true);
    try {
      const enabled = !notificationEnabled;
      const updated = await Promise.all(activeNotificationChannels.map((channel) => (
        upsertNotificationSubscription({
          channel_id: channel.id,
          event_type: "market.session.main_opened",
          subject_type: "market",
          subject_id: selectedMarket.id,
          enabled,
          locale: resolvedLanguage === "zh" ? "zh" : "en",
        })
      )));
      const updatedIds = new Set(updated.map((item) => item.id));
      setNotificationSubscriptions((items) => [
        ...items.filter((item) => !updatedIds.has(item.id)),
        ...updated,
      ]);
      showToast(t(
        enabled ? "marketHours.notifications.enabled" : "marketHours.notifications.disabled",
        { market: localized(selectedMarket.name, resolvedLanguage) },
      ), "success");
    } catch {
      // API helper already shows a localized error.
    } finally {
      setNotificationBusy(false);
    }
  };

  const clock = formatClock(now, referenceTimezone, locale);
  const currentZone = referenceZones.find((zone) => zone.timezone === referenceTimezone);
  const zoneLabel = currentZone
    ? (resolvedLanguage === "zh" ? currentZone.zh : currentZone.en)
    : referenceTimezone.split("_").join(" ");

  return (
    <div className="market-hours-page">
      <main className="flex flex-col gap-3 p-3">
        <Card className="gap-3 rounded-[10px] bg-[var(--panel-card-bg)] py-4">
          <CardContent className="flex flex-col gap-3 px-4">
            <div>
              <div className="flex items-baseline gap-2 tabular-nums">
                <span className="text-[42px] font-semibold leading-none tracking-tight">{clock.time}</span>
                <span className="text-subheading text-muted-foreground">:{clock.seconds}</span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted-foreground">
                <span className="font-semibold text-primary">{formatOffset(now, referenceTimezone, locale)}</span>
                <Select
                  value={referenceTimezone}
                  onValueChange={setReferenceTimezone}
                >
                  <SelectTrigger
                    size="sm"
                    className="h-6 rounded-none border-0 border-b border-transparent bg-transparent px-0 font-medium shadow-none hover:bg-transparent focus-visible:border-[var(--market-info)] focus-visible:ring-0"
                    style={marketHoursControlSizes.inputStyle}
                    aria-label={t("marketHours.referenceTimezone")}
                  >
                    <SelectValue placeholder={zoneLabel} />
                  </SelectTrigger>
                  <SelectContent align="start">
                    {referenceZones.map((zone) => (
                      <SelectItem key={zone.timezone} value={zone.timezone}>
                        {resolvedLanguage === "zh" ? zone.zh : zone.en}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span>{formatDate(now, referenceTimezone, locale)}</span>
                <span className="flex items-center gap-0.5">
                  {data
                    ? t("marketHours.updated", { time: new Date(data.generated_at).toLocaleTimeString(locale) })
                    : t("marketHours.loading")}
                  <TooltipIconButton
                    label={t("marketHours.refresh")}
                    variant="ghost"
                    size={marketHoursControlSizes.refreshAction}
                    className="size-6 rounded-none text-muted-foreground hover:bg-transparent hover:text-foreground"
                    style={marketHoursControlSizes.buttonStyle}
                    onClick={() => void load(false)}
                    disabled={loading}
                  >
                    <RefreshCw className={cn("size-[var(--icon-xs)]", loading && "animate-spin")} />
                  </TooltipIconButton>
                </span>
              </div>
            </div>

            <div className="flex flex-col justify-between gap-2 border-t border-border/50 pt-2 md:flex-row md:items-center">
              <div className="flex items-center gap-2 text-caption text-muted-foreground">
                <span className="size-1.5 rounded-full bg-emerald-500" />
                {t("marketHours.activeCount", { count: activeCount })}
              </div>
              <div className="flex min-w-0 items-center gap-3 overflow-x-auto">
                <span className="shrink-0 text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t("marketHours.filterLabel")}
                </span>
                <ToggleGroup
                  type="single"
                  value={groupFilter}
                  onValueChange={(value) => { if (value) setGroupFilter(value as "all" | MarketHoursGroup); }}
                  variant="default"
                  size="sm"
                  spacing={1}
                  className="h-7 gap-0 rounded-none"
                >
                  {marketGroups.map((group) => (
                    <ToggleGroupItem
                      key={group.value}
                      value={group.value}
                      style={marketHoursControlSizes.buttonStyle}
                      className={marketHoursControlSizes.filterTabClassName}
                    >
                      {t(group.labelKey)}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
                <Button
                  variant="ghost"
                  size="sm"
                  style={marketHoursControlSizes.buttonStyle}
                  className={cn(
                    "h-7 shrink-0 rounded-none px-2.5 font-normal text-muted-foreground hover:bg-transparent hover:text-foreground",
                    openOnly && "text-[var(--market-up)] hover:text-[var(--market-up)]",
                  )}
                  onClick={() => setOpenOnly((value) => !value)}
                  aria-pressed={openOnly}
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full border border-muted-foreground/60",
                      openOnly && "border-[var(--market-up)] bg-[var(--market-up)]",
                    )}
                  />
                  {t("marketHours.onlyOpen")}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {error ? (
          <Card className="rounded-[10px] bg-[var(--panel-card-bg)] py-8">
            <CardContent className="text-center text-ui text-muted-foreground">{t("marketHours.error")}</CardContent>
          </Card>
        ) : data ? (
          <>
            {filteredGroups.length ? (
              <SessionTimeline
                groups={filteredGroups}
                now={now}
                language={resolvedLanguage}
                locale={locale}
                referenceTimezone={referenceTimezone}
                windowStartAt={data.window_start_at}
                windowEndAt={data.window_end_at}
                onSelect={(item) => setSelectedMarketId(item.id)}
                t={t}
              />
            ) : (
              <Card className="rounded-[10px] bg-[var(--panel-card-bg)] py-8">
                <CardContent className="text-center text-ui text-muted-foreground">{t("marketHours.empty")}</CardContent>
              </Card>
            )}

            <div className="flex flex-wrap gap-3 px-1 text-micro text-muted-foreground">
              {(["main", "night", "pre", "after"] as const).map((kind) => (
                <span key={kind} className="flex items-center gap-1.5">
                  <span className={cn("size-2.5 rounded-[3px] border", sessionTone[kind])} />
                  {t(`marketHours.session.${kind}`)}
                </span>
              ))}
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-px bg-primary" />
                {t("marketHours.now")}
              </span>
            </div>

            <ForexSessions
              items={liveForexSessions}
              overlaps={data.forex_overlaps}
              now={now}
              language={resolvedLanguage}
              locale={locale}
              referenceTimezone={referenceTimezone}
              windowStartAt={data.window_start_at}
              windowEndAt={data.window_end_at}
              onSelect={(item) => setSelectedMarketId(item.id)}
              t={t}
            />

            <div className="flex flex-col gap-1 px-1 pb-2 text-micro text-muted-foreground sm:flex-row sm:justify-between">
              <span>{localized(data.calendar_notice, resolvedLanguage)}</span>
              <span>{t("marketHours.scheduleVersion", { version: data.schedule_version })}</span>
            </div>
          </>
        ) : (
          <Card className="rounded-[10px] bg-[var(--panel-card-bg)] py-8">
            <CardContent className="text-center text-ui text-muted-foreground">{t("marketHours.loading")}</CardContent>
          </Card>
        )}
      </main>

      <MarketDetails
        item={selectedMarket}
        open={Boolean(selectedMarketId)}
        onOpenChange={(open) => { if (!open) setSelectedMarketId(null); }}
        now={now}
        language={resolvedLanguage}
        locale={locale}
        referenceTimezone={referenceTimezone}
        notificationEnabled={notificationEnabled}
        notificationBusy={notificationBusy}
        onToggleNotification={() => void toggleOpeningNotification()}
        t={t}
      />
    </div>
  );
}
