import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { calculateDrawdown, type DrawdownResult } from "@/api/client";
import {
  formatMetric,
  MetricGrid,
  NumberField,
  ResultCard,
  ToolFormCard,
  ToolLayout,
  toNumber,
  type LoadJournalToolData,
} from "./shared";

export default function DrawdownTool({ loadMyData }: { loadMyData: LoadJournalToolData }) {
  const { t } = useTranslation();
  const [startingEquity, setStartingEquity] = useState("10000");
  const [currentEquity, setCurrentEquity] = useState("9000");
  const [maxDrawdown, setMaxDrawdown] = useState("20");
  const [riskPercent, setRiskPercent] = useState("1");
  const [result, setResult] = useState<DrawdownResult | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    try {
      setResult(await calculateDrawdown({
        starting_equity: toNumber(startingEquity),
        current_equity: toNumber(currentEquity),
        max_drawdown_percent: toNumber(maxDrawdown),
        risk_per_trade_percent: toNumber(riskPercent),
      }));
    } finally {
      setLoading(false);
    }
  };

  const prefill = async () => {
    const data = await loadMyData();
    if (!data?.startingCapital) return;
    setStartingEquity(String(data.startingCapital));
    setCurrentEquity(String(data.startingCapital + data.stats.total_pnl));
  };

  return (
    <ToolLayout>
      <ToolFormCard title={t("tradingTools.drawdown.formTitle")} description={t("tradingTools.drawdown.formDescription")} loading={loading} onSubmit={submit} onPrefill={() => void prefill()}>
        <NumberField label={t("tradingTools.drawdown.startingEquity")} value={startingEquity} onChange={setStartingEquity} min={0} />
        <NumberField label={t("tradingTools.drawdown.currentEquity")} value={currentEquity} onChange={setCurrentEquity} min={0} />
        <NumberField label={t("tradingTools.drawdown.maxDrawdown")} value={maxDrawdown} onChange={setMaxDrawdown} min={0} max={99} />
        <NumberField label={t("tradingTools.drawdown.riskPercent")} value={riskPercent} onChange={setRiskPercent} min={0} max={99} />
      </ToolFormCard>
      <ResultCard title={t("tradingTools.drawdown.resultTitle")} description={t("tradingTools.drawdown.resultDescription")}>
        {result ? (
          <div className="space-y-4">
            <MetricGrid items={[
              { label: t("tradingTools.drawdown.currentDrawdown"), value: `${formatMetric(result.drawdown_percent)}%`, tone: result.drawdown_percent > 0 ? "danger" : "success" },
              { label: t("tradingTools.drawdown.recoveryGain"), value: `${formatMetric(result.recovery_gain_percent)}%` },
              { label: t("tradingTools.drawdown.floorEquity"), value: formatMetric(result.floor_equity) },
              { label: t("tradingTools.drawdown.remainingBudget"), value: formatMetric(result.remaining_loss_budget) },
              { label: t("tradingTools.drawdown.remainingBudgetPercent"), value: `${formatMetric(result.remaining_budget_percent)}%` },
              { label: t("tradingTools.drawdown.lossCapacity"), value: formatMetric(result.losses_until_limit, 0), tone: result.limit_breached ? "danger" : "default" },
            ]} />
            {result.limit_breached ? (
              <div className="rounded-[var(--radius-md)] border border-destructive/30 bg-destructive/5 px-4 py-3 text-caption text-destructive">
                {t("tradingTools.drawdown.breached")}
              </div>
            ) : null}
          </div>
        ) : undefined}
      </ResultCard>
    </ToolLayout>
  );
}
