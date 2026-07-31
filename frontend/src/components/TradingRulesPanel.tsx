import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  createTradingRule,
  deleteTradingRule,
  listTradingRules,
  setTradingRuleActive,
  type TradingRule,
  type TradingRuleType,
  type TradingRuleWeight,
} from "@/api/client";

const controlStyle = { fontSize: "var(--font-ui)", fontWeight: 400 };
const labelClassName = "text-caption font-medium text-muted-foreground";
const inputClassName = "h-8 placeholder:text-[length:var(--font-caption)]";
const RULE_TYPES: TradingRuleType[] = [
  "max_risk_percent",
  "min_risk_reward",
  "max_trades_per_day",
  "min_confidence",
  "require_stop_loss",
  "require_notes",
];
const NO_THRESHOLD = new Set<TradingRuleType>(["require_stop_loss", "require_notes"]);

export default function TradingRulesPanel() {
  const { t } = useTranslation();
  const [rules, setRules] = useState<TradingRule[]>([]);
  const [open, setOpen] = useState(false);
  const [ruleType, setRuleType] = useState<TradingRuleType>("max_risk_percent");
  const [name, setName] = useState("");
  const [threshold, setThreshold] = useState("");
  const [weight, setWeight] = useState<TradingRuleWeight>("important");

  useEffect(() => {
    listTradingRules().then((result) => setRules(result.items)).catch(() => setRules([]));
  }, []);

  const categories = useMemo(() => ([
    { key: "risk", types: new Set<TradingRuleType>(["max_risk_percent", "min_risk_reward"]) },
    { key: "discipline", types: new Set<TradingRuleType>(["min_confidence", "require_stop_loss", "require_notes"]) },
    { key: "behavior", types: new Set<TradingRuleType>(["max_trades_per_day"]) },
  ]), []);

  const openCreate = () => {
    setRuleType("max_risk_percent");
    setName(t("rules.type.max_risk_percent"));
    setThreshold("1");
    setWeight("important");
    setOpen(true);
  };

  const handleTypeChange = (value: string) => {
    const next = value as TradingRuleType;
    setRuleType(next);
    setName(t(`rules.type.${next}`));
    setThreshold(NO_THRESHOLD.has(next) ? "" : next === "min_confidence" ? "7" : "1");
  };

  const handleCreate = async () => {
    const created = await createTradingRule({
      name: name.trim(),
      rule_type: ruleType,
      threshold: NO_THRESHOLD.has(ruleType) ? null : Number(threshold),
      weight,
    });
    setRules((current) => [...current, created]);
    setOpen(false);
  };

  const toggleRule = async (rule: TradingRule) => {
    const updated = await setTradingRuleActive(rule.id, !rule.active);
    setRules((current) => current.map((item) => item.id === rule.id ? updated : item));
  };

  const removeRule = async (id: string) => {
    await deleteTradingRule(id);
    setRules((current) => current.filter((item) => item.id !== id));
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="title-description-stack">
          <h2 className="text-subheading font-semibold">{t("rules.title")}</h2>
          <p className="text-caption text-muted-foreground">{t("rules.subtitle")}</p>
        </div>
        <TooltipIconButton
          label={t("rules.add")}
          size="icon-sm"
          style={controlStyle}
          onClick={openCreate}
        >
          <Plus />
        </TooltipIconButton>
      </div>

      {rules.length === 0 ? (
        <Card className="py-12"><CardContent className="text-center text-caption text-muted-foreground">{t("rules.empty")}</CardContent></Card>
      ) : categories.map((category) => {
        const categoryRules = rules.filter((rule) => category.types.has(rule.rule_type));
        if (categoryRules.length === 0) return null;
        return (
          <section key={category.key} className="flex flex-col gap-2">
            <div className="text-caption font-semibold uppercase tracking-wide text-muted-foreground">{t(`rules.category.${category.key}`)}</div>
            {categoryRules.map((rule) => (
              <Card key={rule.id} className="py-0 shadow-none">
                <CardContent className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-ui font-semibold">{rule.name}</span>
                      <Badge variant="outline">{t(`rules.weight.${rule.weight}`)}</Badge>
                    </div>
                    <div className="mt-1 text-caption text-muted-foreground">
                      {t(`rules.type.${rule.rule_type}`)}
                      {rule.threshold != null ? ` · ${rule.threshold}` : ""}
                    </div>
                  </div>
                  <Button variant={rule.active ? "secondary" : "outline"} size="sm" style={controlStyle} onClick={() => void toggleRule(rule)}>
                    {t(rule.active ? "rules.active" : "rules.inactive")}
                  </Button>
                  <TooltipIconButton
                    label={t("common.delete")}
                    variant="ghost"
                    size="icon-sm"
                    style={controlStyle}
                    onClick={() => void removeRule(rule.id)}
                  >
                    <Trash2 />
                  </TooltipIconButton>
                </CardContent>
              </Card>
            ))}
          </section>
        );
      })}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle className="text-subheading">{t("rules.add")}</DialogTitle></DialogHeader>
          <FieldGroup className="gap-4">
            <Field><FieldLabel className={labelClassName}>{t("rules.ruleType")}</FieldLabel><Select value={ruleType} onValueChange={handleTypeChange}><SelectTrigger size="sm" style={controlStyle}><SelectValue /></SelectTrigger><SelectContent>{RULE_TYPES.map((type) => <SelectItem key={type} value={type}>{t(`rules.type.${type}`)}</SelectItem>)}</SelectContent></Select></Field>
            <Field><FieldLabel className={labelClassName}>{t("rules.name")}</FieldLabel><Input className={inputClassName} style={controlStyle} value={name} onChange={(e) => setName(e.target.value)} /></Field>
            {!NO_THRESHOLD.has(ruleType) ? <Field><FieldLabel className={labelClassName}>{t("rules.threshold")}</FieldLabel><Input className={inputClassName} type="number" min="0" step="any" style={controlStyle} value={threshold} onChange={(e) => setThreshold(e.target.value)} /></Field> : null}
            <Field><FieldLabel className={labelClassName}>{t("rules.weight")}</FieldLabel><Select value={weight} onValueChange={(value) => setWeight(value as TradingRuleWeight)}><SelectTrigger size="sm" style={controlStyle}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="critical">{t("rules.weight.critical")}</SelectItem><SelectItem value="important">{t("rules.weight.important")}</SelectItem><SelectItem value="nice_to_have">{t("rules.weight.nice_to_have")}</SelectItem></SelectContent></Select></Field>
          </FieldGroup>
          <DialogFooter>
            <Button variant="outline" size="sm" style={controlStyle} onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button size="sm" style={controlStyle} onClick={() => void handleCreate()} disabled={!name.trim() || (!NO_THRESHOLD.has(ruleType) && !threshold)}>{t("journal.save")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
