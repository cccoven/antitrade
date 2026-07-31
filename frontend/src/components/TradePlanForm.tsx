import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import ComplianceSummaryCard from "@/components/ComplianceSummaryCard";
import {
  checkTradeCompliance,
  calculatePositionSize,
  createTradePlan,
  type ComplianceSummary,
  type PositionSizeResult,
  type TradePlan,
} from "@/api/client";
import { listStrategyOptions, type StrategyOption } from "@/api/strategies";
import { journalTradeFormControlSizes } from "@/pages/journal-ui-config";
import { useJournalSettings } from "@/journal/journal-settings-context";

const controlStyle = {
  fontSize: journalTradeFormControlSizes.fieldValueFontSize,
  fontWeight: journalTradeFormControlSizes.fieldValueFontWeight,
};
const labelClassName = "text-caption font-medium text-muted-foreground";
const inputClassName = `h-8 ${journalTradeFormControlSizes.inputPlaceholderClassName}`;

interface TradePlanFormProps {
  open: boolean;
  onClose: () => void;
  onSaved: (plan: TradePlan) => void;
}

export default function TradePlanForm({ open, onClose, onSaved }: TradePlanFormProps) {
  const { t } = useTranslation();
  const { currencyCode, formatMoney } = useJournalSettings();
  const [market, setMarket] = useState("stock");
  const [symbol, setSymbol] = useState("");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [entryPrice, setEntryPrice] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [accountSize, setAccountSize] = useState("10000");
  const [riskPercent, setRiskPercent] = useState("1");
  const [thesis, setThesis] = useState("");
  const [strategyId, setStrategyId] = useState("");
  const [strategyOptions, setStrategyOptions] = useState<StrategyOption[]>([]);
  const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
  const [calculation, setCalculation] = useState<PositionSizeResult | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    listStrategyOptions().then(setStrategyOptions).catch(() => setStrategyOptions([]));
    setCompliance(null);
  }, [open]);

  useEffect(() => {
    const entry = Number(entryPrice);
    const stop = Number(stopLoss);
    const account = Number(accountSize);
    const riskPct = Number(riskPercent);
    if (!open || !symbol.trim() || !entry || !stop || !account || !riskPct || entry === stop) {
      setCalculation(null);
      return;
    }
    let active = true;
    const timer = window.setTimeout(() => {
      calculatePositionSize({
        asset_class: market as "stock" | "forex" | "crypto" | "futures",
        symbol: symbol.trim(),
        direction,
        entry_price: entry,
        stop_loss: stop,
        target_price: targetPrice ? Number(targetPrice) : null,
        account_size: account,
        risk_percent: riskPct,
      }).then((result) => {
        if (active) setCalculation(result);
      }).catch(() => {
        if (active) setCalculation(null);
      });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [accountSize, direction, entryPrice, market, open, riskPercent, stopLoss, symbol, targetPrice]);

  const payload = () => ({
    symbol: symbol.trim(),
    market,
    direction,
    entry_price: Number(entryPrice),
    target_price: targetPrice ? Number(targetPrice) : null,
    stop_loss: Number(stopLoss),
    account_size: Number(accountSize),
    risk_percent: Number(riskPercent),
    thesis,
    strategy_id: strategyId || null,
  });

  const canSubmit = Boolean(
    symbol.trim()
    && Number(entryPrice)
    && Number(stopLoss)
    && Number(entryPrice) !== Number(stopLoss)
    && Number(accountSize) > 0
    && Number(riskPercent) > 0,
  );

  const handleCheck = async () => {
    if (!canSubmit) return;
    const next = await checkTradeCompliance({
      symbol: symbol.trim(),
      direction,
      entry_price: Number(entryPrice),
      target_price: targetPrice ? Number(targetPrice) : null,
      stop_loss: Number(stopLoss),
      quantity: calculation?.quantity ?? null,
      account_size: Number(accountSize),
      thesis,
    });
    setCompliance(next);
  };

  const handleSave = async () => {
    if (!canSubmit) return;
    setSaving(true);
    try {
      const plan = await createTradePlan(payload());
      onSaved(plan);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="right" showCloseButton={false} className="trade-form border-l-0 p-0">
        <SheetHeader className="trade-form-head border-b border-border">
          <SheetTitle className="trade-form-title">{t("tradePlan.new")}</SheetTitle>
        </SheetHeader>
        <div className="trade-form-body">
          <FieldGroup className="gap-4">
            <div className="trade-form-row">
              <Field className="flex-1">
                <FieldLabel className={labelClassName}>{t("tradePlan.market")}</FieldLabel>
                <Select value={market} onValueChange={setMarket}>
                  <SelectTrigger style={controlStyle}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stock">{t("tradePlan.market.stock")}</SelectItem>
                    <SelectItem value="futures">{t("tradePlan.market.futures")}</SelectItem>
                    <SelectItem value="forex">{t("tradePlan.market.forex")}</SelectItem>
                    <SelectItem value="crypto">{t("tradePlan.market.crypto")}</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field className="flex-1">
                <FieldLabel htmlFor="plan-symbol" className={labelClassName}>{t("journal.symbol")}</FieldLabel>
                <Input id="plan-symbol" className={inputClassName} style={controlStyle} value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="NQ" />
              </Field>
            </div>
            <Field>
              <FieldLabel className={labelClassName}>{t("journal.direction")}</FieldLabel>
              <ToggleGroup type="single" variant="outline" size={journalTradeFormControlSizes.toggle} value={direction} onValueChange={(v) => v && setDirection(v as "long" | "short")}>
                <ToggleGroupItem value="long" style={controlStyle} className="flex-1">{t("journal.long")}</ToggleGroupItem>
                <ToggleGroupItem value="short" style={controlStyle} className="flex-1">{t("journal.short")}</ToggleGroupItem>
              </ToggleGroup>
            </Field>
            <div className="grid grid-cols-3 gap-2">
              <Field><FieldLabel className={labelClassName}>{t("tradePlan.entry")}</FieldLabel><Input className={inputClassName} type="number" step="any" style={controlStyle} value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} /></Field>
              <Field><FieldLabel className={labelClassName}>{t("tradePlan.stop")}</FieldLabel><Input className={inputClassName} type="number" step="any" style={controlStyle} value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} /></Field>
              <Field><FieldLabel className={labelClassName}>{t("tradePlan.target")}</FieldLabel><Input className={inputClassName} type="number" step="any" style={controlStyle} value={targetPrice} onChange={(e) => setTargetPrice(e.target.value)} /></Field>
            </div>
            <div className="trade-form-row">
              <Field className="flex-1"><FieldLabel className={labelClassName}>{t("tradePlan.accountSize")}{currencyCode ? ` (${currencyCode})` : ""}</FieldLabel><Input className={inputClassName} type="number" min="0" step="any" style={controlStyle} value={accountSize} onChange={(e) => setAccountSize(e.target.value)} /></Field>
              <Field className="flex-1"><FieldLabel className={labelClassName}>{t("tradePlan.riskPercent")}</FieldLabel><Input className={inputClassName} type="number" min="0" max="100" step="any" style={controlStyle} value={riskPercent} onChange={(e) => setRiskPercent(e.target.value)} /></Field>
            </div>
            {calculation ? (
              <div className="grid grid-cols-3 gap-2 rounded-lg border border-border bg-muted/20 p-3 text-caption">
                <div><span className="text-muted-foreground">{t("tradePlan.riskAmount")}</span><div className="font-semibold tabular-nums">{formatMoney(calculation.risk_budget ?? 0)}</div></div>
                <div><span className="text-muted-foreground">{t("tradePlan.quantity")}</span><div className="font-semibold tabular-nums">{calculation.quantity == null ? "—" : calculation.quantity.toFixed(2)}</div></div>
                <div><span className="text-muted-foreground">R:R</span><div className="font-semibold tabular-nums">{calculation.reward_risk == null ? "—" : calculation.reward_risk.toFixed(2)}</div></div>
              </div>
            ) : null}
            <Field>
              <FieldLabel className={labelClassName}>{t("strategies.linkLabel")}</FieldLabel>
              <Select value={strategyId || "__none__"} onValueChange={(v) => setStrategyId(v === "__none__" ? "" : v)}>
                <SelectTrigger style={controlStyle}><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">{t("strategies.linkPlaceholder")}</SelectItem>
                  {strategyOptions.map((option) => <SelectItem key={option.id} value={option.id}>{option.title || "Untitled"}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
            <Field><FieldLabel className={labelClassName}>{t("tradePlan.thesis")}</FieldLabel><Textarea rows={4} style={controlStyle} value={thesis} onChange={(e) => setThesis(e.target.value)} /></Field>
            {compliance ? <ComplianceSummaryCard summary={compliance} /> : null}
          </FieldGroup>
        </div>
        <SheetFooter className="trade-form-footer border-t border-border">
          <div className="flex w-full gap-2">
            <Button variant="outline" size="sm" style={controlStyle} onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="outline" size="sm" style={controlStyle} onClick={handleCheck} disabled={!canSubmit}>{t("compliance.check")}</Button>
            <Button size="sm" className="flex-1" style={controlStyle} onClick={handleSave} disabled={!canSubmit || saving}>{t("journal.save")}</Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
