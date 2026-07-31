import type { FormEvent, ReactNode } from "react";
import { Calculator, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { tradingToolsControlSizes } from "@/pages/trading-tools-ui-config";

export interface JournalToolData {
  startingCapital: number | null;
  stats: {
    total_trades: number;
    win_rate: number;
    avg_win: number;
    avg_loss: number;
    gross_total_pnl: number;
    total_fees: number;
    total_pnl: number;
  };
}

export type LoadJournalToolData = () => Promise<JournalToolData | null>;

export function toNumber(value: string): number {
  return Number(value.trim());
}

export function optionalNumber(value: string): number | null {
  return value.trim() ? Number(value) : null;
}

export function formatMetric(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

export function ToolLayout({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">{children}</div>;
}

export function ToolFormCard({
  title,
  description,
  children,
  loading,
  onSubmit,
  onPrefill,
}: {
  title: string;
  description: string;
  children: ReactNode;
  loading: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onPrefill?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit}>
        <CardContent className="grid gap-4 sm:grid-cols-2">{children}</CardContent>
        <CardFooter className="mt-5 justify-between gap-3">
          {onPrefill ? (
            <Button type="button" variant="outline" size="sm" style={tradingToolsControlSizes.buttonStyle} onClick={onPrefill}>
              {t("tradingTools.useMyData")}
            </Button>
          ) : <span />}
          <Button type="submit" size="sm" style={tradingToolsControlSizes.buttonStyle} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : <Calculator />}
            {t("tradingTools.calculate")}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

export function NumberField({
  label,
  value,
  onChange,
  description,
  min,
  max,
  step = "any",
  required = true,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  description?: string;
  min?: number;
  max?: number;
  step?: number | "any";
  required?: boolean;
}) {
  return (
    <Field>
      <FieldLabel className="text-caption">{label}</FieldLabel>
      <Input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        required={required}
        style={tradingToolsControlSizes.inputStyle}
        onChange={(event) => onChange(event.target.value)}
      />
      {description ? <FieldDescription className="text-caption">{description}</FieldDescription> : null}
    </Field>
  );
}

export function ResultCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <Card className="min-h-[320px]">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {children ?? (
          <div className="flex flex-1 items-center justify-center rounded-[var(--radius-md)] border border-dashed border-border bg-muted/35 px-6 text-center text-caption text-muted-foreground">
            {t("tradingTools.emptyResult")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MetricGrid({
  items,
}: {
  items: { label: string; value: string; tone?: "default" | "success" | "danger" }[];
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.label} className="rounded-[var(--radius-md)] border border-border bg-muted/35 px-4 py-3">
          <div className="text-caption text-muted-foreground">{item.label}</div>
          <div
            className="mt-1 text-subheading font-semibold tabular-nums"
            style={{
              color: item.tone === "success"
                ? "var(--success)"
                : item.tone === "danger"
                  ? "var(--danger)"
                  : undefined,
            }}
          >
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}
