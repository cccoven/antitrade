import { useMemo, useState, type FormEvent } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";

import { calculateMonteCarlo, type MonteCarloResult } from "@/api/client";
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

export default function MonteCarloTool({ loadMyData }: { loadMyData: LoadJournalToolData }) {
  const { t } = useTranslation();
  const [startingEquity, setStartingEquity] = useState("10000");
  const [targetReturn, setTargetReturn] = useState("10");
  const [maxDrawdown, setMaxDrawdown] = useState("20");
  const [winRate, setWinRate] = useState("55");
  const [avgWinR, setAvgWinR] = useState("1.5");
  const [avgLossR, setAvgLossR] = useState("1");
  const [riskPercent, setRiskPercent] = useState("1");
  const [trades, setTrades] = useState("100");
  const [simulations, setSimulations] = useState("1000");
  const [result, setResult] = useState<MonteCarloResult | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    try {
      setResult(await calculateMonteCarlo({
        starting_equity: toNumber(startingEquity),
        target_return_percent: toNumber(targetReturn),
        max_drawdown_percent: toNumber(maxDrawdown),
        win_rate: toNumber(winRate),
        avg_win_r: toNumber(avgWinR),
        avg_loss_r: toNumber(avgLossR),
        risk_per_trade_percent: toNumber(riskPercent),
        trades: Math.round(toNumber(trades)),
        simulations: Math.round(toNumber(simulations)),
        seed: 42,
      }));
    } finally {
      setLoading(false);
    }
  };

  const prefill = async () => {
    const data = await loadMyData();
    if (!data) return;
    if (data.startingCapital) setStartingEquity(String(data.startingCapital));
    if (data.stats.total_trades > 0) {
      setWinRate(String(data.stats.win_rate * 100));
      if (data.stats.avg_loss !== 0) {
        setAvgWinR(String(data.stats.avg_win / Math.abs(data.stats.avg_loss)));
        setAvgLossR("1");
      }
    }
  };

  const chartOption = useMemo(() => {
    if (!result) return null;
    const style = getComputedStyle(document.documentElement);
    const text = style.getPropertyValue("--text-secondary").trim();
    const border = style.getPropertyValue("--border").trim();
    const accent = style.getPropertyValue("--accent").trim() || "#b88352";
    const success = style.getPropertyValue("--success").trim() || "#299764";
    const danger = style.getPropertyValue("--danger").trim() || "#d05e4d";
    const panel = style.getPropertyValue("--panel-bg").trim() || "#1a1a1a";
    const foreground = style.getPropertyValue("--text-primary").trim();
    return {
      grid: { left: 58, right: 12, top: 34, bottom: 34 },
      tooltip: { trigger: "axis" as const, backgroundColor: panel, borderColor: border, textStyle: { color: foreground, fontSize: 12 } },
      legend: { top: 0, right: 0, textStyle: { color: text, fontSize: 10 } },
      xAxis: {
        type: "category" as const,
        data: result.percentile_bands.map((item) => item.trade),
        axisLabel: { color: text, fontSize: 10 },
        axisLine: { lineStyle: { color: border } },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: { color: text, fontSize: 10 },
        splitLine: { lineStyle: { color: border, type: "dashed" as const } },
      },
      series: [
        { name: "P10", type: "line" as const, data: result.percentile_bands.map((item) => item.p10), symbol: "none", smooth: true, lineStyle: { color: danger, width: 1.5 } },
        { name: "P50", type: "line" as const, data: result.percentile_bands.map((item) => item.p50), symbol: "none", smooth: true, lineStyle: { color: accent, width: 2 } },
        { name: "P90", type: "line" as const, data: result.percentile_bands.map((item) => item.p90), symbol: "none", smooth: true, lineStyle: { color: success, width: 1.5 } },
      ],
    };
  }, [result]);

  return (
    <ToolLayout>
      <ToolFormCard title={t("tradingTools.monteCarlo.formTitle")} description={t("tradingTools.monteCarlo.formDescription")} loading={loading} onSubmit={submit} onPrefill={() => void prefill()}>
        <NumberField label={t("tradingTools.monteCarlo.startingEquity")} value={startingEquity} onChange={setStartingEquity} min={0} />
        <NumberField label={t("tradingTools.monteCarlo.targetReturn")} value={targetReturn} onChange={setTargetReturn} min={0} />
        <NumberField label={t("tradingTools.monteCarlo.maxDrawdown")} value={maxDrawdown} onChange={setMaxDrawdown} min={0} max={99} />
        <NumberField label={t("tradingTools.monteCarlo.winRate")} value={winRate} onChange={setWinRate} min={0} max={100} />
        <NumberField label={t("tradingTools.monteCarlo.avgWinR")} value={avgWinR} onChange={setAvgWinR} min={0} />
        <NumberField label={t("tradingTools.monteCarlo.avgLossR")} value={avgLossR} onChange={setAvgLossR} min={0} />
        <NumberField label={t("tradingTools.monteCarlo.riskPercent")} value={riskPercent} onChange={setRiskPercent} min={0} max={99} />
        <NumberField label={t("tradingTools.monteCarlo.trades")} value={trades} onChange={setTrades} min={1} max={2000} step={1} />
        <NumberField label={t("tradingTools.monteCarlo.simulations")} value={simulations} onChange={setSimulations} min={100} max={5000} step={100} />
      </ToolFormCard>
      <ResultCard title={t("tradingTools.monteCarlo.resultTitle")} description={t("tradingTools.monteCarlo.resultDescription")}>
        {result && chartOption ? (
          <div className="space-y-4">
            <MetricGrid items={[
              { label: t("tradingTools.monteCarlo.targetProbability"), value: `${formatMetric(result.target_probability)}%`, tone: "success" },
              { label: t("tradingTools.monteCarlo.riskOfRuin"), value: `${formatMetric(result.risk_of_ruin)}%`, tone: result.risk_of_ruin > 10 ? "danger" : "default" },
              { label: t("tradingTools.monteCarlo.medianEnding"), value: formatMetric(result.median_ending_equity) },
              { label: t("tradingTools.monteCarlo.p90Drawdown"), value: `${formatMetric(result.p90_max_drawdown)}%` },
            ]} />
            <ReactECharts option={chartOption} style={{ height: 250 }} opts={{ renderer: "svg" }} />
          </div>
        ) : undefined}
      </ResultCard>
    </ToolLayout>
  );
}
