import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { calculateCostImpact, type CostImpactResult } from "@/api/client";
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

export default function CostImpactTool({ loadMyData }: { loadMyData: LoadJournalToolData }) {
  const { t } = useTranslation();
  const [trades, setTrades] = useState("100");
  const [grossPnl, setGrossPnl] = useState("2000");
  const [commission, setCommission] = useState("2");
  const [slippage, setSlippage] = useState("1");
  const [spread, setSpread] = useState("0");
  const [result, setResult] = useState<CostImpactResult | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    try {
      setResult(await calculateCostImpact({
        trades_count: Math.round(toNumber(trades)),
        gross_pnl: toNumber(grossPnl),
        commission_per_trade: toNumber(commission),
        slippage_per_trade: toNumber(slippage),
        spread_per_trade: toNumber(spread),
      }));
    } finally {
      setLoading(false);
    }
  };

  const prefill = async () => {
    const data = await loadMyData();
    if (!data || data.stats.total_trades === 0) return;
    setTrades(String(data.stats.total_trades));
    setGrossPnl(String(data.stats.gross_total_pnl));
    setCommission(String(data.stats.total_fees / data.stats.total_trades));
    setSlippage("0");
    setSpread("0");
  };

  return (
    <ToolLayout>
      <ToolFormCard title={t("tradingTools.cost.formTitle")} description={t("tradingTools.cost.formDescription")} loading={loading} onSubmit={submit} onPrefill={() => void prefill()}>
        <NumberField label={t("tradingTools.cost.trades")} value={trades} onChange={setTrades} min={1} step={1} />
        <NumberField label={t("tradingTools.cost.grossPnl")} value={grossPnl} onChange={setGrossPnl} />
        <NumberField label={t("tradingTools.cost.commission")} value={commission} onChange={setCommission} min={0} />
        <NumberField label={t("tradingTools.cost.slippage")} value={slippage} onChange={setSlippage} min={0} />
        <NumberField label={t("tradingTools.cost.spread")} value={spread} onChange={setSpread} min={0} />
      </ToolFormCard>
      <ResultCard title={t("tradingTools.cost.resultTitle")} description={t("tradingTools.cost.resultDescription")}>
        {result ? <MetricGrid items={[
          { label: t("tradingTools.cost.netPnl"), value: formatMetric(result.net_pnl), tone: result.net_pnl >= 0 ? "success" : "danger" },
          { label: t("tradingTools.cost.totalCost"), value: formatMetric(result.total_cost), tone: "danger" },
          { label: t("tradingTools.cost.costPerTrade"), value: formatMetric(result.cost_per_trade) },
          { label: t("tradingTools.cost.grossAverage"), value: formatMetric(result.gross_average) },
          { label: t("tradingTools.cost.netAverage"), value: formatMetric(result.net_average) },
          { label: t("tradingTools.cost.dragPercent"), value: `${formatMetric(result.cost_drag_percent)}%` },
        ]} /> : undefined}
      </ResultCard>
    </ToolLayout>
  );
}
