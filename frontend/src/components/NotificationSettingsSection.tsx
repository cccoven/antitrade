import { useCallback, useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Send, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  connectDiscord,
  connectTelegram,
  deleteNotificationChannel,
  listNotificationChannels,
  listNotificationDeliveries,
  listNotificationSubscriptions,
  testNotificationChannel,
  type NotificationChannel,
  type NotificationDelivery,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { showToast } from "@/components/Toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/i18n/i18n-context";
import { cn } from "@/lib/utils";

const buttonStyle = { fontSize: "var(--font-ui)" };
const inputStyle = { fontSize: "var(--font-ui)" };

export default function NotificationSettingsSection() {
  const { t } = useTranslation();
  const { resolvedLanguage } = useI18n();
  const { user, setLoginDialogOpen } = useAuth();
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [deliveries, setDeliveries] = useState<NotificationDelivery[]>([]);
  const [subscriptionCount, setSubscriptionCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [discordWebhookUrl, setDiscordWebhookUrl] = useState("");

  const load = useCallback(async (quiet = false) => {
    if (!user) return;
    if (!quiet) setLoading(true);
    try {
      const [nextChannels, nextSubscriptions, nextDeliveries] = await Promise.all([
        listNotificationChannels(),
        listNotificationSubscriptions(),
        listNotificationDeliveries(10),
      ]);
      setChannels(nextChannels);
      setSubscriptionCount(nextSubscriptions.filter((item) => item.enabled).length);
      setDeliveries(nextDeliveries);
    } catch {
      // API helper already shows a localized error.
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [user]);

  useEffect(() => { void load(false); }, [load]);

  const telegram = useMemo(
    () => channels.find((channel) => channel.channel_type === "telegram") ?? null,
    [channels],
  );
  const inApp = useMemo(
    () => channels.find((channel) => channel.channel_type === "in_app") ?? null,
    [channels],
  );
  const discord = useMemo(
    () => channels.find((channel) => channel.channel_type === "discord") ?? null,
    [channels],
  );

  useEffect(() => {
    if (!user || telegram?.status !== "pending") return;
    const timer = window.setInterval(() => { void load(true); }, 3_000);
    return () => window.clearInterval(timer);
  }, [load, telegram?.status, user]);

  const handleTelegramConnect = async () => {
    if (!user) {
      setLoginDialogOpen(true);
      return;
    }
    setWorking(true);
    try {
      const result = await connectTelegram(resolvedLanguage === "zh" ? "zh" : "en");
      window.open(result.deep_link, "_blank", "noopener,noreferrer");
      await load(true);
    } catch {
      // API helper already shows a localized error.
    } finally {
      setWorking(false);
    }
  };

  const handleDiscordConnect = async () => {
    const webhookUrl = discordWebhookUrl.trim();
    if (!webhookUrl) return;
    setWorking(true);
    try {
      await connectDiscord(webhookUrl, resolvedLanguage === "zh" ? "zh" : "en");
      setDiscordWebhookUrl("");
      showToast(t("notifications.discord.connected"), "success");
      await load(true);
    } catch {
      // API helper already shows a localized error.
    } finally {
      setWorking(false);
    }
  };

  const handleTest = async (channel: NotificationChannel) => {
    setWorking(true);
    try {
      await testNotificationChannel(channel.id);
      showToast(t("notifications.testSent"), "success");
      await load(true);
    } catch {
      // API helper already shows a localized error.
    } finally {
      setWorking(false);
    }
  };

  const handleDisconnect = async (channel: NotificationChannel) => {
    setWorking(true);
    try {
      await deleteNotificationChannel(channel.id);
      await load(true);
    } catch {
      // API helper already shows a localized error.
    } finally {
      setWorking(false);
    }
  };

  if (!user) {
    return (
      <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5">
        <div className="text-ui font-medium">{t("notifications.loginRequired")}</div>
        <Button className="mt-3" size="sm" style={buttonStyle} onClick={() => setLoginDialogOpen(true)}>
          {t("auth.login")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-7">
      <section>
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-ui font-semibold text-foreground">{t("notifications.channels")}</span>
          <Button
            variant="ghost"
            size="icon-sm"
            style={buttonStyle}
            disabled={loading || working}
            onClick={() => void load(false)}
            aria-label={t("notifications.refresh")}
            title={t("notifications.refresh")}
          >
            <RefreshCw className={cn(loading && "animate-spin")} />
          </Button>
        </div>
        <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)]">
          <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-ui font-medium">{t("notifications.inApp.name")}</span>
                <Badge
                  variant="outline"
                  className="border-emerald-500/40 text-micro text-emerald-600 dark:text-emerald-400"
                >
                  {t("notifications.inApp.builtIn")}
                </Badge>
              </div>
              <div className="mt-1 text-caption text-muted-foreground">
                {inApp
                  ? t("notifications.inApp.description")
                  : t("common.loading")}
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-4 border-t border-border p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-ui font-medium">Telegram</span>
                <Badge variant="outline" className={cn(
                  "text-micro",
                  telegram?.status === "active" && "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
                )}>
                  {telegram?.status === "active"
                    ? t("notifications.status.active")
                    : telegram?.status === "pending"
                      ? t("notifications.status.pending")
                      : t("notifications.status.inactive")}
                </Badge>
              </div>
              <div className="mt-1 truncate text-caption text-muted-foreground">
                {telegram?.status === "active"
                  ? telegram.name
                  : telegram?.status === "pending"
                    ? t("notifications.telegram.pending")
                    : t("notifications.telegram.notConnected")}
              </div>
              {telegram?.status === "pending" ? (
                <div className="mt-2 text-caption text-muted-foreground">
                  {t("notifications.telegram.instructions")}
                </div>
              ) : null}
            </div>

            <div className="flex shrink-0 flex-wrap gap-2">
              {telegram?.status === "active" ? (
                <>
                  <Button variant="outline" size="sm" style={buttonStyle} disabled={working} onClick={() => void handleTest(telegram)}>
                    <Send />
                    {t("notifications.test")}
                  </Button>
                  <Button variant="outline" size="sm" style={buttonStyle} disabled={working} onClick={() => void handleDisconnect(telegram)}>
                    <Trash2 />
                    {t("notifications.disconnect")}
                  </Button>
                </>
              ) : (
                <Button size="sm" style={buttonStyle} disabled={working} onClick={() => void handleTelegramConnect()}>
                  <ExternalLink />
                  {telegram?.status === "pending"
                    ? t("notifications.telegram.continue")
                    : t("notifications.telegram.connect")}
                </Button>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-4 border-t border-border p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-ui font-medium">Discord</span>
                <Badge variant="outline" className={cn(
                  "text-micro",
                  discord?.status === "active" && "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
                )}>
                  {discord?.status === "active"
                    ? t("notifications.status.active")
                    : t("notifications.status.inactive")}
                </Badge>
              </div>
              <div className="mt-1 truncate text-caption text-muted-foreground">
                {discord?.status === "active" ? discord.name : t("notifications.discord.notConnected")}
              </div>
              {discord?.status !== "active" ? (
                <div className="mt-2 text-caption text-muted-foreground">
                  {t("notifications.discord.instructions")}
                </div>
              ) : null}
            </div>

            {discord?.status === "active" ? (
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button variant="outline" size="sm" style={buttonStyle} disabled={working} onClick={() => void handleTest(discord)}>
                  <Send />
                  {t("notifications.test")}
                </Button>
                <Button variant="outline" size="sm" style={buttonStyle} disabled={working} onClick={() => void handleDisconnect(discord)}>
                  <Trash2 />
                  {t("notifications.disconnect")}
                </Button>
              </div>
            ) : (
              <form
                className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:min-w-80"
                onSubmit={(event) => {
                  event.preventDefault();
                  void handleDiscordConnect();
                }}
              >
                <Input
                  type="password"
                  autoComplete="off"
                  style={inputStyle}
                  value={discordWebhookUrl}
                  onChange={(event) => setDiscordWebhookUrl(event.target.value)}
                  placeholder={t("notifications.discord.webhookPlaceholder")}
                  aria-label={t("notifications.discord.webhookPlaceholder")}
                  disabled={working}
                />
                <Button type="submit" size="sm" style={buttonStyle} disabled={working || !discordWebhookUrl.trim()}>
                  <ExternalLink />
                  {t("notifications.discord.connect")}
                </Button>
              </form>
            )}
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-ui font-semibold text-foreground">{t("notifications.subscriptions")}</span>
          <span className="text-caption text-muted-foreground">{t("notifications.subscriptionCount", { count: subscriptionCount })}</span>
        </div>
        <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5 text-caption text-muted-foreground">
          {t("notifications.subscriptionHint")}
        </div>
      </section>

      <section>
        <div className="mb-3 text-ui font-semibold text-foreground">{t("notifications.recent")}</div>
        <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)]">
          {deliveries.length ? deliveries.map((delivery, index) => (
            <div key={delivery.id} className={cn(
              "flex items-center justify-between gap-3 px-5 py-4",
              index > 0 && "border-t border-border",
            )}>
              <div className="min-w-0">
                <div className="truncate text-ui font-medium text-foreground">{delivery.title}</div>
                <div className="mt-1 text-caption text-muted-foreground">
                  {new Date(delivery.created_at).toLocaleString(resolvedLanguage === "zh" ? "zh-CN" : "en-US")}
                </div>
              </div>
              <Badge variant="outline" className="text-micro">{t(`notifications.delivery.${delivery.status}`)}</Badge>
            </div>
          )) : (
            <div className="px-5 py-8 text-center text-caption text-muted-foreground">
              {t("notifications.noDeliveries")}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
