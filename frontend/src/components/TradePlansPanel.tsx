import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, Trash2 } from "lucide-react";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deleteTradePlan, listTradePlans, type TradePlan } from "@/api/client";
import { journalTableControlSizes } from "@/pages/journal-ui-config";
import { cn } from "@/lib/utils";

const buttonStyle = { fontSize: "var(--font-ui)" };
const tableHeadClassName =
  "h-10 bg-[color-mix(in_srgb,var(--chip-bg)_70%,transparent)] px-3 text-caption font-medium tracking-[0.03em] text-muted-foreground";

export default function TradePlansPanel({
  refreshKey,
  onConvert,
  showEmpty = false,
}: {
  refreshKey: number;
  onConvert: (plan: TradePlan) => void;
  showEmpty?: boolean;
}) {
  const { t } = useTranslation();
  const [plans, setPlans] = useState<TradePlan[] | null>(null);

  useEffect(() => {
    listTradePlans().then((result) => setPlans(result.items)).catch(() => setPlans([]));
  }, [refreshKey]);

  const handleDelete = async (id: string) => {
    await deleteTradePlan(id);
    setPlans((current) => current?.filter((plan) => plan.id !== id) ?? []);
  };

  if (plans === null) return null;

  if (plans.length === 0) {
    if (!showEmpty) return null;
    return (
      <Empty className="min-h-[240px] border border-dashed border-border bg-[var(--chip-bg)]">
        <EmptyHeader>
          <EmptyTitle className="text-subheading text-foreground">
            {t("tradePlan.empty")}
          </EmptyTitle>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <Card className="gap-0 py-0">
      <CardHeader className="border-b border-border/50 px-4 py-3">
        <CardTitle>{t("tradePlan.active")}</CardTitle>
      </CardHeader>
      <CardContent className="px-4 py-4">
        <Table className="min-w-[960px] table-fixed">
          <colgroup>
            <col className="w-[14%]" />
            <col className="w-[11%]" />
            <col className="w-[13%]" />
            <col className="w-[12%]" />
            <col className="w-[12%]" />
            <col className="w-[16%]" />
            <col className="w-[8%]" />
            <col className="w-[14%]" />
          </colgroup>
          <TableHeader className="[&_tr]:border-b-0">
            <TableRow>
              <TableHead className={cn(tableHeadClassName, "rounded-l-[10px]")}>{t("journal.symbol")}</TableHead>
              <TableHead className={tableHeadClassName}>{t("journal.direction")}</TableHead>
              <TableHead className={cn(tableHeadClassName, "text-right")}>{t("tradePlan.entry")}</TableHead>
              <TableHead className={cn(tableHeadClassName, "text-right")}>{t("tradePlan.stop")}</TableHead>
              <TableHead className={cn(tableHeadClassName, "text-right")}>{t("tradePlan.target")}</TableHead>
              <TableHead className={cn(tableHeadClassName, "text-right")}>{t("tradePlan.quantity")}</TableHead>
              <TableHead className={cn(tableHeadClassName, "text-right")}>R:R</TableHead>
              <TableHead className={cn(tableHeadClassName, "rounded-r-[10px] text-right")}>{t("journal.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {plans.map((plan) => (
              <TableRow key={plan.id} className="border-b border-border/60">
                <TableCell className="px-3 py-3 text-ui font-semibold text-foreground">{plan.symbol}</TableCell>
                <TableCell className="px-3 py-3">
                  <Badge
                    variant="ghost"
                    className={cn(
                      "rounded-md border border-transparent px-2 py-0.5",
                      journalTableControlSizes.directionBadgeText,
                      plan.direction === "long"
                        ? "bg-[color-mix(in_srgb,var(--success)_12%,transparent)] text-[var(--success)]"
                        : "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)] text-[var(--danger)]"
                    )}
                  >
                    {t(`journal.${plan.direction}`)}
                  </Badge>
                </TableCell>
                <TableCell className="px-3 py-3 text-right text-ui tabular-nums">{plan.entry_price}</TableCell>
                <TableCell className="px-3 py-3 text-right text-ui tabular-nums">{plan.stop_loss}</TableCell>
                <TableCell className="px-3 py-3 text-right text-ui tabular-nums">{plan.target_price ?? "—"}</TableCell>
                <TableCell className="px-3 py-3 text-right text-ui tabular-nums">{plan.quantity?.toFixed(2) ?? "—"}</TableCell>
                <TableCell className="px-3 py-3 text-right text-ui tabular-nums">{plan.risk_reward?.toFixed(2) ?? "—"}</TableCell>
                <TableCell className="px-3 py-3 text-right">
                  <div className="flex justify-end gap-1.5">
                    <TooltipIconButton
                      label={t("tradePlan.convert")}
                      variant="outline"
                      size={journalTableControlSizes.rowAction}
                      style={buttonStyle}
                      onClick={() => onConvert(plan)}
                    >
                      <ArrowRight />
                    </TooltipIconButton>
                    <TooltipIconButton
                      label={t("common.delete")}
                      variant="outline"
                      size={journalTableControlSizes.rowAction}
                      style={buttonStyle}
                      onClick={() => void handleDelete(plan.id)}
                    >
                      <Trash2 />
                    </TooltipIconButton>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
