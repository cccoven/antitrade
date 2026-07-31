import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { calculatePositionSize, type PositionSizeResult, type TradingToolAssetClass } from "@/api/client";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { tradingToolsControlSizes } from "@/pages/trading-tools-ui-config";
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

export default function PositionSizeTool({ loadMyData }: { loadMyData: LoadJournalToolData }) {
  const { t } = useTranslation();
  const [assetClass, setAssetClass] = useState<TradingToolAssetClass>("futures");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [symbol, setSymbol] = useState("MNQ");
  const [entry, setEntry] = useState("20000");
  const [stop, setStop] = useState("19990");
  const [target, setTarget] = useState("20020");
  const [account, setAccount] = useState("10000");
  const [riskPercent, setRiskPercent] = useState("1");
  const [pointValue, setPointValue] = useState("");
  const [result, setResult] = useState<PositionSizeResult | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    try {
      setResult(await calculatePositionSize({
        asset_class: assetClass,
        symbol: symbol.trim(),
        direction,
        entry_price: toNumber(entry),
        stop_loss: toNumber(stop),
        target_price: optionalNumber(target),
        account_size: toNumber(account),
        risk_percent: toNumber(riskPercent),
        point_value: optionalNumber(pointValue),
      }));
    } finally {
      setLoading(false);
    }
  };

  const prefill = async () => {
    const data = await loadMyData();
    if (data?.startingCapital) setAccount(String(data.startingCapital));
  };

  return (
    <ToolLayout>
      <ToolFormCard
        title={t("tradingTools.position.formTitle")}
        description={t("tradingTools.position.formDescription")}
        loading={loading}
        onSubmit={submit}
        onPrefill={() => void prefill()}
      >
        <Field>
          <FieldLabel className="text-caption">{t("tradingTools.position.assetClass")}</FieldLabel>
          <Select value={assetClass} onValueChange={(value) => setAssetClass(value as TradingToolAssetClass)}>
            <SelectTrigger size="sm" style={tradingToolsControlSizes.inputStyle}><SelectValue /></SelectTrigger>
            <SelectContent>
              {(["stock", "forex", "crypto", "futures"] as const).map((item) => (
                <SelectItem key={item} value={item}>{t(`tradingTools.assetClass.${item}`)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel className="text-caption">{t("tradingTools.position.direction")}</FieldLabel>
          <Select value={direction} onValueChange={(value) => setDirection(value as "long" | "short")}>
            <SelectTrigger size="sm" style={tradingToolsControlSizes.inputStyle}><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="long">{t("tradingTools.direction.long")}</SelectItem>
              <SelectItem value="short">{t("tradingTools.direction.short")}</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel className="text-caption">{t("tradingTools.position.symbol")}</FieldLabel>
          <Input value={symbol} required style={tradingToolsControlSizes.inputStyle} onChange={(event) => setSymbol(event.target.value)} />
        </Field>
        <NumberField label={t("tradingTools.position.accountSize")} value={account} onChange={setAccount} min={0} />
        <NumberField label={t("tradingTools.position.entry")} value={entry} onChange={setEntry} min={0} />
        <NumberField label={t("tradingTools.position.stop")} value={stop} onChange={setStop} min={0} />
        <NumberField label={t("tradingTools.position.target")} value={target} onChange={setTarget} min={0} required={false} />
        <NumberField label={t("tradingTools.position.riskPercent")} value={riskPercent} onChange={setRiskPercent} min={0} max={100} />
        <Field className="sm:col-span-2">
          <FieldLabel className="text-caption">{t("tradingTools.position.pointValue")}</FieldLabel>
          <Input type="number" min="0" step="any" value={pointValue} style={tradingToolsControlSizes.inputStyle} onChange={(event) => setPointValue(event.target.value)} />
          <FieldDescription className="text-caption">{t("tradingTools.position.pointValueDescription")}</FieldDescription>
        </Field>
      </ToolFormCard>
      <ResultCard title={t("tradingTools.position.resultTitle")} description={t("tradingTools.position.resultDescription")}>
        {result ? (
          <div className="space-y-4">
            <MetricGrid items={[
              { label: t("tradingTools.position.quantity"), value: formatMetric(result.quantity, 4) },
              { label: t("tradingTools.position.riskBudget"), value: formatMetric(result.risk_budget) },
              { label: t("tradingTools.position.actualRisk"), value: formatMetric(result.risk_amount) },
              { label: t("tradingTools.position.unitRisk"), value: formatMetric(result.unit_risk) },
              { label: "R:R", value: formatMetric(result.reward_risk) },
              { label: t("tradingTools.position.potentialReward"), value: formatMetric(result.potential_reward) },
            ]} />
            {result.warnings.length ? (
              <div className="rounded-[var(--radius-md)] border border-destructive/30 bg-destructive/5 px-4 py-3 text-caption text-destructive">
                {result.warnings.map((warning) => t(`tradingTools.warning.${warning}`)).join(" · ")}
              </div>
            ) : null}
          </div>
        ) : undefined}
      </ResultCard>
    </ToolLayout>
  );
}
