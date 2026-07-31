import { useState } from "react";
import { Check, Crown, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/auth/auth-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useBilling } from "./billing-context";

const controlStyle = { fontSize: "var(--font-ui)" };

function formatMinorAmount(amount: number, currency: string, locale: string): string {
  const formatter = new Intl.NumberFormat(locale, { style: "currency", currency });
  const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2;
  return formatter.format(amount / (10 ** digits));
}

export default function BillingSettingsSection() {
  const { t, i18n } = useTranslation();
  const { user, setLoginDialogOpen } = useAuth();
  const { summary, loading, refresh, startCheckout, manageBilling } = useBilling();
  const [working, setWorking] = useState<"month" | "year" | "portal" | null>(null);

  if (!user) {
    return (
      <div className="rounded-[12px] border border-border bg-[var(--panel-card-bg)] p-5">
        <div className="text-ui font-medium text-foreground">{t("billing.loginRequired")}</div>
        <Button
          className="mt-3"
          size="sm"
          style={controlStyle}
          onClick={() => setLoginDialogOpen(true)}
        >
          {t("auth.login")}
        </Button>
      </div>
    );
  }

  if (!summary && loading) {
    return (
      <div className="flex items-center gap-2 text-ui text-muted-foreground">
        <LoaderCircle className="size-[var(--icon-sm)] animate-spin" />
        {t("billing.loading")}
      </div>
    );
  }

  if (!summary) {
    return (
      <Button variant="outline" size="sm" style={controlStyle} onClick={() => void refresh()}>
        {t("billing.retry")}
      </Button>
    );
  }

  const percent = summary.usage.limit > 0
    ? Math.min(100, Math.round((summary.usage.used / summary.usage.limit) * 100))
    : 0;
  const currency = summary.prices.currency;
  const monthly = formatMinorAmount(summary.prices.monthly, currency, i18n.language);
  const yearly = formatMinorAmount(summary.prices.yearly, currency, i18n.language);

  const checkout = async (interval: "month" | "year") => {
    setWorking(interval);
    try {
      await startCheckout(interval);
    } catch {
      // The API client already shows a safe error.
    } finally {
      setWorking(null);
    }
  };

  const openPortal = async () => {
    setWorking("portal");
    try {
      await manageBilling();
    } catch {
      // The API client already shows a safe error.
    } finally {
      setWorking(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <section className="overflow-hidden rounded-[12px] border border-border bg-[var(--panel-card-bg)]">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-primary/10 text-primary">
              <Crown className="size-[var(--icon-sm)]" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-ui font-semibold text-foreground">
                  {summary.plan === "pro" ? "AntiTrade Pro" : "AntiTrade Free"}
                </span>
                <Badge variant={summary.plan === "pro" ? "default" : "secondary"}>
                  {t(`billing.plan.${summary.plan}`)}
                </Badge>
              </div>
              <div className="mt-1 text-caption text-muted-foreground">
                {summary.plan === "pro"
                  ? t(summary.cancel_at_period_end ? "billing.renews.cancelled" : "billing.renews.active", {
                      date: summary.current_period_end
                        ? new Date(summary.current_period_end).toLocaleDateString(i18n.language)
                        : "—",
                    })
                  : t("billing.free.description")}
              </div>
            </div>
          </div>
          {summary.plan === "pro" ? (
            <Button
              variant="outline"
              size="sm"
              style={controlStyle}
              disabled={working !== null}
              onClick={() => void openPortal()}
            >
              {working === "portal" ? <LoaderCircle className="animate-spin" /> : null}
              {t("billing.manage")}
            </Button>
          ) : null}
        </div>

        <div className="border-t border-border px-5 py-4">
          <div className="flex items-center justify-between gap-3 text-caption">
            <span className="font-medium text-foreground">{t("billing.usage.title")}</span>
            <span className="text-muted-foreground">
              {t("billing.usage.value", {
                used: summary.usage.used,
                limit: summary.usage.limit,
              })}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${percent}%` }} />
          </div>
          <div className="mt-2 text-micro text-muted-foreground">
            {t("billing.usage.resets", {
              date: new Date(summary.usage.resets_at).toLocaleDateString(i18n.language),
            })}
          </div>
        </div>
      </section>

      {summary.plan === "free" ? (
        <section>
          <div className="mb-3 text-ui font-semibold text-foreground">{t("billing.choosePlan")}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            <PlanCard
              title={t("billing.monthly")}
              price={monthly}
              suffix={t("billing.perMonth")}
              working={working === "month"}
              disabled={!summary.stripe_configured || working !== null}
              action={t("billing.subscribeMonthly")}
              onClick={() => void checkout("month")}
            />
            <PlanCard
              title={t("billing.yearly")}
              price={yearly}
              suffix={t("billing.perYear")}
              working={working === "year"}
              disabled={!summary.stripe_configured || working !== null}
              action={t("billing.subscribeYearly")}
              recommended
              onClick={() => void checkout("year")}
            />
          </div>
          {!summary.stripe_configured ? (
            <div className="mt-3 text-caption text-muted-foreground">{t("billing.upgrade.notConfigured")}</div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function PlanCard({
  title,
  price,
  suffix,
  action,
  recommended = false,
  working,
  disabled,
  onClick,
}: {
  title: string;
  price: string;
  suffix: string;
  action: string;
  recommended?: boolean;
  working: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className={`rounded-[12px] border p-5 ${recommended ? "border-primary/60 bg-primary/5" : "border-border bg-[var(--panel-card-bg)]"}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-ui font-semibold text-foreground">{title}</span>
        {recommended ? <Badge>{t("billing.recommended")}</Badge> : null}
      </div>
      <div className="mt-3 flex items-end gap-1">
        <span className="text-heading font-semibold text-foreground">{price}</span>
        <span className="pb-0.5 text-caption text-muted-foreground">{suffix}</span>
      </div>
      <div className="mt-4 grid gap-2">
        {(["research", "vision", "review", "usage"] as const).map((benefit) => (
          <div key={benefit} className="flex items-center gap-2 text-caption text-muted-foreground">
            <Check className="size-[var(--icon-xs)] text-primary" />
            {t(`billing.benefit.${benefit}`)}
          </div>
        ))}
      </div>
      <Button
        className="mt-5 w-full"
        variant={recommended ? "default" : "outline"}
        size="sm"
        style={controlStyle}
        disabled={disabled}
        onClick={onClick}
      >
        {working ? <LoaderCircle className="animate-spin" /> : null}
        {action}
      </Button>
    </div>
  );
}
