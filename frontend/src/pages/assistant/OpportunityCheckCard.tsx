import { CircleAlert, ClipboardCheck, History, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ComplianceSummaryCard from "@/components/ComplianceSummaryCard";
import { cn } from "@/lib/utils";
import type { OpportunityCheckArtifactData } from "@/api/client";
import { MarketSnapshotCard } from "./MarketSnapshotCard";

function formatNumber(value: number | null | undefined, locale: string, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value);
}

export function OpportunityCheckCard({ data }: { data: OpportunityCheckArtifactData }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage || i18n.language;

  if (data.error) {
    return (
      <Card className="mb-3 gap-0 rounded-lg border-destructive/30 bg-destructive/5 py-0 shadow-none">
        <CardContent className="flex items-start gap-2 px-3 py-3 text-caption text-muted-foreground">
          <CircleAlert className="mt-0.5 size-[var(--icon-sm)] shrink-0 text-destructive" />
          <div>
            <div className="font-medium text-foreground">{t("assistant.check.unavailable")}</div>
            <div className="mt-0.5">{t(`assistant.check.error.${data.error}`, { defaultValue: data.error })}</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const opportunity = data.opportunity;
  const risk = data.risk;
  const history = data.history;
  const verdict = data.verdict ?? "insufficient_data";
  const verdictTone = verdict === "compliant"
    ? "text-[var(--success)] border-[var(--success)]/30 bg-[var(--success)]/5"
    : verdict === "adjust"
      ? "text-[var(--danger)] border-[var(--danger)]/30 bg-[var(--danger)]/5"
      : "text-muted-foreground border-border bg-muted/25";

  return (
    <div className="mb-3 w-full">
      {data.market ? <MarketSnapshotCard data={data.market} /> : null}
      <Card className="gap-0 rounded-lg bg-[var(--panel-card-bg)] py-0 shadow-none">
        <CardHeader className="flex flex-row items-center justify-between gap-3 border-b border-border px-3 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <ShieldCheck className="size-[var(--icon-sm)] shrink-0 text-primary" />
            <div>
              <CardTitle>{t("assistant.check.title")}</CardTitle>
              {opportunity ? (
                <div className="mt-0.5 text-micro text-muted-foreground">
                  {opportunity.symbol} · {t(`assistant.check.direction.${opportunity.direction}`)}
                </div>
              ) : null}
            </div>
          </div>
          <Badge variant="outline" className={cn("text-micro", verdictTone)}>
            {t(`assistant.check.verdict.${verdict}`)}
          </Badge>
        </CardHeader>

        <CardContent className="grid gap-3 px-3 py-3">
          {opportunity ? (
            <section>
              <div className="mb-1.5 text-caption font-medium">{t("assistant.check.opportunity")}</div>
              <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                {[
                  [t("assistant.check.entry"), opportunity.entry_price],
                  [t("assistant.check.stop"), opportunity.stop_loss],
                  [t("assistant.check.target"), opportunity.target_price],
                  [t("assistant.check.deviation"), opportunity.entry_deviation_percent, "%"],
                ].map(([label, value, suffix]) => (
                  <div key={String(label)} className="rounded-md bg-muted/35 px-2 py-1.5">
                    <div className="text-micro text-muted-foreground">{label}</div>
                    <div className="mt-0.5 text-caption font-medium tabular-nums">
                      {formatNumber(value as number | null, locale, 4)}{value != null ? suffix : null}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {risk ? (
            <section>
              <div className="mb-1.5 flex items-center gap-1.5 text-caption font-medium">
                <ClipboardCheck className="size-[var(--icon-xs)]" />{t("assistant.check.risk")}
              </div>
              <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                {[
                  [t("assistant.check.riskAmount"), risk.risk_amount],
                  [t("assistant.check.riskPercent"), risk.risk_percent, "%"],
                  [t("assistant.check.rewardRisk"), risk.reward_risk, "R"],
                  [t("assistant.check.maxQuantity"), risk.max_quantity],
                ].map(([label, value, suffix]) => (
                  <div key={String(label)} className="rounded-md border border-border px-2 py-1.5">
                    <div className="text-micro text-muted-foreground">{label}</div>
                    <div className="mt-0.5 text-caption font-medium tabular-nums">
                      {formatNumber(value as number | null, locale, 4)}{value != null ? suffix : null}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {data.plan_match?.plan ? (
            <section className="rounded-md border border-border px-2.5 py-2">
              <div className="text-caption font-medium">{t("assistant.check.planMatched")}</div>
              <div className="mt-1 text-micro text-muted-foreground">
                {data.plan_match.plan.symbol} · {t("assistant.check.planLevels", {
                  entry: formatNumber(data.plan_match.plan.entry_price, locale, 4),
                  stop: formatNumber(data.plan_match.plan.stop_loss, locale, 4),
                  target: formatNumber(data.plan_match.plan.target_price, locale, 4),
                })}
              </div>
            </section>
          ) : null}

          {data.compliance ? <ComplianceSummaryCard summary={data.compliance} /> : null}

          {history ? (
            <section>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 text-caption font-medium">
                  <History className="size-[var(--icon-xs)]" />{t("assistant.check.history")}
                </div>
                <Badge variant="secondary" className="text-micro">
                  {t(`assistant.check.sample.${history.sample_quality}`)} · n={history.sample_count}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                {[
                  [t("assistant.check.winRate"), history.win_rate, "%"],
                  [t("assistant.check.averagePnl"), history.average_pnl],
                  [t("assistant.check.profitFactor"), history.profit_factor],
                  [t("assistant.check.expectancy"), history.expectancy],
                ].map(([label, value, suffix]) => (
                  <div key={String(label)} className="rounded-md bg-muted/35 px-2 py-1.5">
                    <div className="text-micro text-muted-foreground">{label}</div>
                    <div className="mt-0.5 text-caption font-medium tabular-nums">
                      {formatNumber(value as number | null, locale, 2)}{value != null ? suffix : null}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {data.warnings?.length ? (
            <div className="flex items-start gap-1.5 rounded-md bg-muted/25 px-2.5 py-2 text-micro text-muted-foreground">
              <CircleAlert className="mt-0.5 size-[var(--icon-xs)] shrink-0" />
              <span>{data.warnings.map((warning) => t(`assistant.check.warning.${warning}`, { defaultValue: warning })).join(" · ")}</span>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
