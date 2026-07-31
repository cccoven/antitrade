import { useState } from "react";
import { Check, Crown, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useBilling } from "./billing-context";

const controlStyle = { fontSize: "var(--font-ui)" };

function formatMinorAmount(amount: number, currency: string, locale: string): string {
  const formatter = new Intl.NumberFormat(locale, { style: "currency", currency });
  const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2;
  return formatter.format(amount / (10 ** digits));
}

export default function BillingUpgradeDialog() {
  const { t, i18n } = useTranslation();
  const {
    summary,
    upgradeOpen,
    upgradeFeature,
    closeUpgrade,
    startCheckout,
  } = useBilling();
  const [working, setWorking] = useState<"month" | "year" | null>(null);

  const checkout = async (interval: "month" | "year") => {
    setWorking(interval);
    try {
      await startCheckout(interval);
      closeUpgrade();
    } catch {
      // The API client already surfaces a safe user-facing error.
    } finally {
      setWorking(null);
    }
  };

  const currency = summary?.prices.currency ?? "USD";
  const monthly = formatMinorAmount(summary?.prices.monthly ?? 900, currency, i18n.language);
  const yearly = formatMinorAmount(summary?.prices.yearly ?? 9000, currency, i18n.language);
  const configured = summary?.stripe_configured ?? false;

  return (
    <Dialog open={upgradeOpen} onOpenChange={(open) => { if (!open) closeUpgrade(); }}>
      <DialogContent className="sm:max-w-[560px]" showCloseButton={false}>
        <DialogHeader>
          <div className="mb-1 flex size-10 items-center justify-center rounded-[12px] bg-primary/10 text-primary">
            <Crown className="size-[var(--icon-md)]" />
          </div>
          <DialogTitle>{t("billing.upgrade.title")}</DialogTitle>
          <DialogDescription>
            {upgradeFeature
              ? t("billing.upgrade.featureReason", { feature: t(`billing.feature.${upgradeFeature}`) })
              : t("billing.upgrade.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-2 rounded-[12px] border border-border bg-muted/30 p-4 sm:grid-cols-2">
          {(["research", "vision", "review", "usage"] as const).map((benefit) => (
            <div key={benefit} className="flex items-start gap-2 text-ui text-foreground">
              <Check className="mt-0.5 size-[var(--icon-xs)] shrink-0 text-primary" />
              <span>{t(`billing.benefit.${benefit}`)}</span>
            </div>
          ))}
        </div>

        {!configured ? (
          <div className="rounded-[10px] border border-border bg-muted/30 px-3 py-2 text-caption text-muted-foreground">
            {t("billing.upgrade.notConfigured")}
          </div>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            size="sm"
            style={controlStyle}
            onClick={closeUpgrade}
          >
            {t("billing.upgrade.keepFree")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            style={controlStyle}
            disabled={!configured || working !== null}
            onClick={() => void checkout("month")}
          >
            {working === "month" ? <LoaderCircle className="animate-spin" /> : null}
            {t("billing.upgrade.monthly", { price: monthly })}
          </Button>
          <Button
            type="button"
            size="sm"
            style={controlStyle}
            disabled={!configured || working !== null}
            onClick={() => void checkout("year")}
          >
            {working === "year" ? <LoaderCircle className="animate-spin" /> : null}
            {t("billing.upgrade.yearly", { price: yearly })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
