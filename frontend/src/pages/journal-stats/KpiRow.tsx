import { useTranslation } from "react-i18next";
import { ChevronDown, CircleHelp } from "lucide-react";
import type { TradeStats } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { useJournalSettings } from "@/journal/journal-settings-context";
import { formatPct, pnlColor } from "./journal-stats-format";

interface KpiRowProps {
  stats: TradeStats;
  expanded: boolean;
  onToggle: () => void;
}

export default function KpiRow({ stats, expanded, onToggle }: KpiRowProps) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();

  return (
    <div className="flex gap-3 flex-wrap">
      <ExpandableCard
        label={t("journal.kpi.totalPnl")}
        value={displayMoney(stats.total_pnl, { signed: true })}
        valueColor={pnlColor(stats.total_pnl)}
        active={expanded}
        onClick={onToggle}
      />
      <StaticCard label={t("journal.kpi.winRate")} value={formatPct(stats.win_rate)} />
      <StaticCard
        label={t("journal.kpi.profitFactor")}
        value={(stats.profit_factor ?? 0).toFixed(2)}
        help={t("journal.kpi.help.profitFactor")}
      />
      <StaticCard
        label={t("journal.kpi.maxDrawdown")}
        value={displayMoney(-stats.max_drawdown, { signed: true })}
        valueColor={stats.max_drawdown > 0 ? "var(--danger)" : undefined}
        help={t("journal.kpi.help.maxDrawdown")}
      />
      <StaticCard
        label={t("journal.kpi.sharpe")}
        value={(stats.sharpe_ratio ?? 0).toFixed(2)}
        help={t("journal.kpi.help.sharpe")}
      />
    </div>
  );
}

function HelpIcon({ text }: { text: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-[var(--text-faint)] hover:text-[var(--text-primary)] transition-colors"
          aria-label="Explain this metric"
          onClick={(e) => e.stopPropagation()}
        >
          <CircleHelp className="size-[var(--icon-xs)]" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 text-caption leading-relaxed" align="start">
        {text}
      </PopoverContent>
    </Popover>
  );
}

function StaticCard({
  label,
  value,
  valueColor,
  help,
}: {
  label: string;
  value: string;
  valueColor?: string;
  help?: string;
}) {
  return (
    <Card className="min-w-[132px] flex-1 gap-3 py-4">
      <CardHeader className="gap-1 px-4 pb-0 flex flex-row items-center justify-between">
        <CardDescription>{label}</CardDescription>
        {help && <HelpIcon text={help} />}
      </CardHeader>
      <CardContent className="px-4 pt-0">
        <div
          className="font-semibold leading-none text-heading"
          style={valueColor ? { color: valueColor } : undefined}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function ExpandableCard({
  label,
  value,
  valueColor,
  active,
  onClick,
}: {
  label: string;
  value: string;
  valueColor?: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Card
      role="button"
      tabIndex={0}
      aria-expanded={active}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        "min-w-[132px] flex-1 gap-3 py-4 cursor-pointer transition-colors",
        "hover:bg-[var(--chip-bg-strong)]",
        active && "ring-2 ring-[var(--accent-strong)]",
      )}
    >
      <CardHeader className="gap-1 px-4 pb-0 flex flex-row items-center justify-between">
        <CardDescription>{label}</CardDescription>
        <ChevronDown
          className={cn(
            "size-[var(--icon-xs)] text-[var(--text-faint)] transition-transform",
            active && "rotate-180",
          )}
        />
      </CardHeader>
      <CardContent className="px-4 pt-0">
        <div
          className="font-semibold leading-none text-heading"
          style={valueColor ? { color: valueColor } : undefined}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
