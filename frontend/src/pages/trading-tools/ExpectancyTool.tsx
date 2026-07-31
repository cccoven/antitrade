import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { calculateExpectancy, type ExpectancyResult } from "@/api/client";
import {
  formatMetric,
  MetricGrid,
  NumberField,
  optionalNumber,
  ResultCard,
  ToolFormCard,
  ToolLayout,
  toNumber,
  type LoadJournalToolData,
} from "./shared";

export default function ExpectancyTool({ loadMyData }: { loadMyData: LoadJournalToolData }) {
  const { t } = useTranslation();
  const [winRate, setWinRate] = useState("55");
  const [avgWin, setAvgWin] = useState("150");
  const [avgLoss, setAvgLoss] = useState("100");
  const [cost, setCost] = useState("5");
  const [target, setTarget] = useState("1000");
  const [result, setResult] = useState<ExpectancyResult | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    try {
      setResult(await calculateExpectancy({
        win_rate: toNumber(winRate),
        avg_win: toNumber(avgWin),
        avg_loss: toNumber(avgLoss),
        cost_per_trade: toNumber(cost),
        target_profit: optionalNumber(target),
      }));
    } finally {
      setLoading(false);
    }
  };

  const prefill = async () => {
    const data = await loadMyData();
    if (!data || data.stats.total_trades === 0) return;
    setWinRate(String(data.stats.win_rate * 100));
    setAvgWin(String(data.stats.avg_win));
    setAvgLoss(String(Math.abs(data.stats.avg_loss)));
    setCost(String(data.stats.total_fees / data.stats.total_trades));
  };

  return (
    <ToolLayout>
      <ToolFormCard title={t("tradingTools.expectancy.formTitle")} description={t("tradingTools.expectancy.formDescription")} loading={loading} onSubmit={submit} onPrefill={() => void prefill()}>
        <NumberField label={t("tradingTools.expectancy.winRate")} value={winRate} onChange={setWinRate} min={0} max={100} />
        <NumberField label={t("tradingTools.expectancy.avgWin")} value={avgWin} onChange={setAvgWin} min={0} />
        <NumberField label={t("tradingTools.expectancy.avgLoss")} value={avgLoss} onChange={setAvgLoss} min={0} />
        <NumberField label={t("tradingTools.expectancy.cost")} value={cost} onChange={setCost} min={0} />
        <NumberField label={t("tradingTools.expectancy.target")} value={target} onChange={setTarget} min={0} required={false} />
      </ToolFormCard>
      <ResultCard title={t("tradingTools.expectancy.resultTitle")} description={t("tradingTools.expectancy.resultDescription")}>
        {result ? <MetricGrid items={[
          { label: t("tradingTools.expectancy.netExpectancy"), value: formatMetric(result.expectancy), tone: result.expectancy >= 0 ? "success" : "danger" },
          { label: t("tradingTools.expectancy.grossExpectancy"), value: formatMetric(result.gross_expectancy) },
          { label: t("tradingTools.expectancy.breakEven"), value: `${formatMetric(result.break_even_win_rate)}%` },
          { label: t("tradingTools.expectancy.profitFactor"), value: formatMetric(result.gross_profit_factor) },
          { label: t("tradingTools.expectancy.costDrag"), value: formatMetric(result.cost_drag), tone: "danger" },
          { label: t("tradingTools.expectancy.tradesToTarget"), value: formatMetric(result.trades_to_target, 0) },
        ]} /> : undefined}
      </ResultCard>
    </ToolLayout>
  );
}
