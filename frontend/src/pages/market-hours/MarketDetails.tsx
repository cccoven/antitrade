import type { MarketHoursItem } from "@/api/client";
import { Bell, BellOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/use-mobile";
import { marketHoursControlSizes } from "../market-hours-ui-config";
import {
  formatCountdown,
  localized,
  visibleSessionLabel,
} from "./market-hours-utils";

export default function MarketDetails({
  item,
  open,
  onOpenChange,
  now,
  language,
  locale,
  referenceTimezone,
  notificationEnabled,
  notificationBusy,
  onToggleNotification,
  t,
}: {
  item: MarketHoursItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  now: Date;
  language: string;
  locale: string;
  referenceTimezone: string;
  notificationEnabled: boolean;
  notificationBusy: boolean;
  onToggleNotification: () => void;
  t: (key: string) => string;
}) {
  const isMobile = useIsMobile();
  if (!item) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side={isMobile ? "bottom" : "right"} className={isMobile ? "max-h-[82vh]" : undefined}>
        <SheetHeader className="border-b border-border">
          <div className="flex items-center gap-2 pr-10">
            <SheetTitle>{localized(item.name, language)}</SheetTitle>
            <Badge variant="outline" className="text-micro">
              {t(`marketHours.state.${item.state}`)}
            </Badge>
          </div>
          <SheetDescription>{localized(item.city, language)}</SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-[18px] py-2">
          <div>
            <div className="text-caption font-semibold text-foreground">{t("marketHours.details.timezone")}</div>
            <div className="mt-1 text-ui text-muted-foreground">{item.timezone}</div>
          </div>
          <div>
            <div className="text-caption font-semibold text-foreground">{t("marketHours.details.nextTransition")}</div>
            <div className="mt-1 text-ui text-muted-foreground">
              {formatCountdown(item.next_transition_at, now, language)}
            </div>
          </div>
          <div>
            <div className="text-caption font-semibold text-foreground">{t("marketHours.details.referenceSessions")}</div>
            <div className="mt-2 flex flex-col gap-2">
              {item.sessions.length ? item.sessions.map((session, index) => (
                <div key={`${session.start_at}-${index}`} className="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2">
                  <span className="text-caption text-muted-foreground">{t(`marketHours.session.${session.kind}`)}</span>
                  <span className="text-ui font-medium tabular-nums">
                    {visibleSessionLabel(session, referenceTimezone, locale)}
                  </span>
                </div>
              )) : (
                <div className="text-ui text-muted-foreground">{t("marketHours.details.noSessions")}</div>
              )}
            </div>
          </div>
          {item.notification_capabilities.includes("market.session.main_opened") ? (
            <div className="rounded-md border border-border bg-muted/30 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-caption font-semibold text-foreground">{t("marketHours.notifications.title")}</div>
                  <div className="mt-1 text-caption text-muted-foreground">{t("marketHours.notifications.description")}</div>
                </div>
                <Button
                  variant={notificationEnabled ? "secondary" : "outline"}
                  size="sm"
                  style={marketHoursControlSizes.buttonStyle}
                  disabled={notificationBusy}
                  onClick={onToggleNotification}
                  aria-pressed={notificationEnabled}
                >
                  {notificationEnabled ? <BellOff /> : <Bell />}
                  {notificationEnabled
                    ? t("marketHours.notifications.disable")
                    : t("marketHours.notifications.enable")}
                </Button>
              </div>
            </div>
          ) : null}
          {item.note ? (
            <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-caption text-muted-foreground">
              {localized(item.note, language)}
            </div>
          ) : null}
        </div>
        <SheetFooter className="border-t border-border">
          <SheetClose asChild>
            <Button variant="outline" size="sm" style={marketHoursControlSizes.buttonStyle}>
              {t("marketHours.details.close")}
            </Button>
          </SheetClose>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
