import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck, Inbox, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  deleteNotificationInboxMessage,
  getNotificationInboxUnreadCount,
  listNotificationInbox,
  markAllNotificationInboxRead,
  markNotificationInboxRead,
  type NotificationInboxItem,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  animatedLineTabClassName,
  Tabs,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useI18n } from "@/i18n/i18n-context";
import { cn } from "@/lib/utils";

const buttonStyle = { fontSize: "var(--font-ui)" };

function formatNotificationTime(value: string, locale: "zh" | "en") {
  return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function NotificationInbox({
  collapsed,
}: {
  collapsed: boolean;
}) {
  const { t } = useTranslation();
  const { resolvedLanguage } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(false);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [items, setItems] = useState<NotificationInboxItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [working, setWorking] = useState(false);

  const refreshUnreadCount = useCallback(async () => {
    if (!user) {
      setUnreadCount(0);
      return;
    }
    try {
      setUnreadCount(await getNotificationInboxUnreadCount(true));
    } catch {
      // Background polling stays quiet during transient failures.
    }
  }, [user]);

  const loadInbox = useCallback(async (
    cursor: string | null = null,
    append = false,
  ) => {
    if (!user) return;
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const page = await listNotificationInbox({
        unreadOnly: filter === "unread",
        cursor,
        limit: 20,
      });
      setItems((current) => append ? [...current, ...page.items] : page.items);
      setNextCursor(page.next_cursor);
      setUnreadCount(page.unread_count);
    } catch {
      // API helper already shows localized user-facing copy.
    } finally {
      if (append) setLoadingMore(false);
      else setLoading(false);
    }
  }, [filter, resolvedLanguage, user]);

  useEffect(() => {
    if (!user) {
      setItems([]);
      setUnreadCount(0);
      return;
    }
    void refreshUnreadCount();
    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") void refreshUnreadCount();
    };
    const timer = window.setInterval(refreshIfVisible, 30_000);
    window.addEventListener("focus", refreshIfVisible);
    document.addEventListener("visibilitychange", refreshIfVisible);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshIfVisible);
      document.removeEventListener("visibilitychange", refreshIfVisible);
    };
  }, [refreshUnreadCount, user]);

  useEffect(() => {
    if (open) void loadInbox();
  }, [loadInbox, open]);

  useEffect(() => {
    setHover(false);
  }, [collapsed]);

  const markRead = async (item: NotificationInboxItem) => {
    if (item.read_at) return;
    const readAt = new Date().toISOString();
    setItems((current) => filter === "unread"
      ? current.filter((candidate) => candidate.id !== item.id)
      : current.map((candidate) => (
          candidate.id === item.id ? { ...candidate, read_at: readAt } : candidate
        )));
    setUnreadCount((count) => Math.max(0, count - 1));
    try {
      await markNotificationInboxRead(item.id);
    } catch {
      await loadInbox();
    }
  };

  const handleItemClick = async (item: NotificationInboxItem) => {
    await markRead(item);
    if (item.action_url?.startsWith("/")) {
      setOpen(false);
      navigate(item.action_url);
    }
  };

  const handleMarkAllRead = async () => {
    setWorking(true);
    const readAt = new Date().toISOString();
    setItems((current) => current.map((item) => (
      item.read_at ? item : { ...item, read_at: readAt }
    )));
    setUnreadCount(0);
    try {
      await markAllNotificationInboxRead();
      if (filter === "unread") await loadInbox();
    } catch {
      await loadInbox();
    } finally {
      setWorking(false);
    }
  };

  const handleDelete = async (item: NotificationInboxItem) => {
    setItems((current) => current.filter((candidate) => candidate.id !== item.id));
    if (!item.read_at) {
      setUnreadCount((count) => Math.max(0, count - 1));
    }
    try {
      await deleteNotificationInboxMessage(item.id);
    } catch {
      await loadInbox();
    }
  };

  if (!user) return null;

  const countLabel = unreadCount > 99 ? "99+" : String(unreadCount);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <Tooltip open={collapsed && hover}>
        <TooltipTrigger asChild>
          <SheetTrigger asChild>
            <button
              type="button"
              className="sidebar-settings-btn relative"
              onMouseEnter={() => setHover(true)}
              onMouseLeave={() => setHover(false)}
              aria-label={t("notifications.inbox.title")}
            >
              <Bell />
              <span className="sidebar-settings-label">
                {t("notifications.inbox.title")}
              </span>
              {unreadCount > 0 ? (
                <span className={cn(
                  "flex min-w-4 items-center justify-center rounded-full bg-primary px-1 text-micro font-semibold leading-4 text-primary-foreground",
                  collapsed
                    ? "absolute -right-1 -top-1 h-4"
                    : "ml-auto h-4",
                )}>
                  {countLabel}
                </span>
              ) : null}
            </button>
          </SheetTrigger>
        </TooltipTrigger>
        <TooltipContent side="right">
          {t("notifications.inbox.title")}
        </TooltipContent>
      </Tooltip>

      <SheetContent className="gap-0 overflow-hidden">
        <SheetHeader className="border-b border-border pr-16">
          <div className="flex items-center justify-between gap-3">
            <SheetTitle>{t("notifications.inbox.title")}</SheetTitle>
            <Button
              variant="ghost"
              size="sm"
              style={buttonStyle}
              disabled={working || unreadCount === 0}
              onClick={() => void handleMarkAllRead()}
            >
              <CheckCheck />
              {t("notifications.inbox.markAllRead")}
            </Button>
          </div>
          <SheetDescription>
            {t("notifications.inbox.description")}
          </SheetDescription>
        </SheetHeader>

        <div className="border-b border-border px-[18px] py-3">
          <Tabs
            value={filter}
            className="gap-0"
            onValueChange={(value) => {
              if (value === "all" || value === "unread") setFilter(value);
            }}
          >
            <TabsList variant="line" className="h-7 gap-3 p-0">
              <TabsTrigger
                value="all"
                style={buttonStyle}
                className={animatedLineTabClassName}
              >
                {t("notifications.inbox.all")}
              </TabsTrigger>
              <TabsTrigger
                value="unread"
                style={buttonStyle}
                className={animatedLineTabClassName}
              >
                {t("notifications.inbox.unread")}
                {unreadCount > 0 ? ` ${unreadCount}` : ""}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          {loading ? (
            <div className="px-5 py-12 text-center text-caption text-muted-foreground">
              {t("common.loading")}
            </div>
          ) : items.length === 0 ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-3 px-5 text-center">
              <span className="flex size-10 items-center justify-center rounded-full bg-muted">
                <Inbox className="size-[var(--icon-md)] text-muted-foreground" />
              </span>
              <div>
                <div className="text-ui font-medium text-foreground">
                  {t("notifications.inbox.empty")}
                </div>
                <div className="mt-1 text-caption text-muted-foreground">
                  {t("notifications.inbox.emptyHint")}
                </div>
              </div>
            </div>
          ) : (
            <div>
              {items.map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    "flex w-full items-start gap-2 border-b border-border px-[18px] py-4 transition-colors hover:bg-muted/40",
                    !item.read_at && "bg-primary/[0.035]",
                  )}
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 gap-3 text-left"
                    onClick={() => void handleItemClick(item)}
                  >
                    <span className={cn(
                      "mt-1.5 size-2 shrink-0 rounded-full",
                      item.read_at ? "bg-transparent" : "bg-primary",
                    )} />
                    <span className="min-w-0 flex-1">
                      <span className={cn(
                        "block truncate text-ui text-foreground",
                        !item.read_at && "font-semibold",
                      )}>
                        {item.title}
                      </span>
                      {item.body ? (
                        <span className="mt-1 line-clamp-2 block text-caption leading-relaxed text-muted-foreground">
                          {item.body}
                        </span>
                      ) : null}
                      <span className="mt-2 block text-micro text-muted-foreground">
                        {formatNotificationTime(item.occurred_at, resolvedLanguage)}
                      </span>
                    </span>
                  </button>
                  <TooltipIconButton
                    label={t("notifications.inbox.delete")}
                    tooltipSide="left"
                    variant="ghost"
                    size="icon-xs"
                    style={buttonStyle}
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => void handleDelete(item)}
                  >
                    <Trash2 />
                  </TooltipIconButton>
                </div>
              ))}
              {nextCursor ? (
                <div className="flex justify-center px-5 py-4">
                  <Button
                    variant="outline"
                    size="sm"
                    style={buttonStyle}
                    disabled={loadingMore}
                    onClick={() => void loadInbox(nextCursor, true)}
                  >
                    {loadingMore
                      ? t("common.loading")
                      : t("notifications.inbox.loadMore")}
                  </Button>
                </div>
              ) : null}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
