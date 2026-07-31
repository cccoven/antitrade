import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import type { TradeStats } from "@/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { useJournalSettings } from "@/journal/journal-settings-context";
import {
  formatPct,
  formatDuration,
  formatDateTime,
  formatInt,
  pnlColor,
} from "./journal-stats-format";

interface KpiDetailPanelProps {
  stats: TradeStats;
  expanded: boolean;
}

interface DetailRow {
  label: string;
  value: string;
  color?: string;
}

export default function KpiDetailPanel({ stats, expanded }: KpiDetailPanelProps) {
  const { t } = useTranslation();
  const { displayMoney } = useJournalSettings();

  if (!expanded) return null;

  return (
    <Card className="gap-0 py-3">
      <CardContent className="px-6 py-3 grid grid-cols-1 md:grid-cols-3 gap-x-10 gap-y-6">
        <Column title={t("journal.kpi.tab.all")} rows={buildAllRows(stats, t, displayMoney)} />
        <Column title={t("journal.kpi.tab.profit")} rows={buildProfitRows(stats, t, displayMoney)} />
        <Column title={t("journal.kpi.tab.loss")} rows={buildLossRows(stats, t, displayMoney)} />
      </CardContent>
    </Card>
  );
}

function Column({ title, rows }: { title: string; rows: DetailRow[] }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-caption text-muted-foreground uppercase tracking-wider pb-1 border-b border-border">
        {title}
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-ui">
        {rows.map((r) => (
          <Row key={r.label} label={r.label} value={r.value} color={r.color} />
        ))}
      </div>
    </div>
  );
}

function Row({ label, value, color }: DetailRow) {
  return (
    <>
      <div className="text-muted-foreground">{label}</div>
      <div
        className="text-right font-mono"
        style={color ? { color } : undefined}
      >
        {value}
      </div>
    </>
  );
}

type MoneyFormatter = ReturnType<typeof useJournalSettings>["displayMoney"];

function buildAllRows(s: TradeStats, t: TFunction, formatMoney: MoneyFormatter): DetailRow[] {
  return [
    { label: t("journal.kpi.all.grossPnl"), value: formatMoney(s.gross_total_pnl, { signed: true }), color: pnlColor(s.gross_total_pnl) },
    { label: t("journal.kpi.all.numTrades"), value: formatInt(s.total_trades) },
    { label: t("journal.kpi.all.numContracts"), value: formatInt(s.total_contracts) },
    { label: t("journal.kpi.all.avgTradeTime"), value: formatDuration(s.avg_holding_seconds) },
    { label: t("journal.kpi.all.longestTradeTime"), value: formatDuration(s.longest_holding_all) },
    { label: t("journal.kpi.all.percentProfitable"), value: formatPct(s.win_rate) },
    { label: t("journal.kpi.all.feesComm"), value: formatMoney(-s.total_fees, { signed: true }), color: s.total_fees > 0 ? "var(--danger)" : undefined },
    { label: t("journal.kpi.all.totalPnl"), value: formatMoney(s.total_pnl, { signed: true }), color: pnlColor(s.total_pnl) },
  ];
}

function buildProfitRows(s: TradeStats, t: TFunction, formatMoney: MoneyFormatter): DetailRow[] {
  return [
    { label: t("journal.kpi.profit.totalProfit"), value: formatMoney(s.total_profit, { signed: true }), color: "var(--success)" },
    { label: t("journal.kpi.profit.numWinners"), value: formatInt(s.winners) },
    { label: t("journal.kpi.profit.winningContracts"), value: formatInt(s.winning_contracts) },
    { label: t("journal.kpi.profit.largestWin"), value: formatMoney(s.largest_winner, { signed: true }), color: "var(--success)" },
    { label: t("journal.kpi.profit.avgWin"), value: formatMoney(s.avg_win, { signed: true }), color: s.avg_win > 0 ? "var(--success)" : undefined },
    { label: t("journal.kpi.profit.stdWin"), value: formatMoney(s.std_winner) },
    { label: t("journal.kpi.profit.avgWinTime"), value: formatDuration(s.avg_holding_winners) },
    { label: t("journal.kpi.profit.longestWinTime"), value: formatDuration(s.longest_holding_winners) },
    { label: t("journal.kpi.profit.maxRunUp"), value: formatMoney(s.max_run_up, { signed: true }), color: s.max_run_up > 0 ? "var(--success)" : undefined },
    { label: t("journal.kpi.profit.runUpFrom"), value: formatDateTime(s.max_run_up_from) },
    { label: t("journal.kpi.profit.runUpTo"), value: formatDateTime(s.max_run_up_to) },
  ];
}

function buildLossRows(s: TradeStats, t: TFunction, formatMoney: MoneyFormatter): DetailRow[] {
  return [
    { label: t("journal.kpi.loss.totalLoss"), value: formatMoney(s.total_loss, { signed: true }), color: "var(--danger)" },
    { label: t("journal.kpi.loss.numLosers"), value: formatInt(s.losers) },
    { label: t("journal.kpi.loss.losingContracts"), value: formatInt(s.losing_contracts) },
    { label: t("journal.kpi.loss.largestLoss"), value: formatMoney(s.largest_loser, { signed: true }), color: "var(--danger)" },
    { label: t("journal.kpi.loss.avgLoss"), value: formatMoney(s.avg_loss, { signed: true }), color: s.avg_loss < 0 ? "var(--danger)" : undefined },
    { label: t("journal.kpi.loss.stdLoss"), value: formatMoney(s.std_loser) },
    { label: t("journal.kpi.loss.avgLossTime"), value: formatDuration(s.avg_holding_losers) },
    { label: t("journal.kpi.loss.longestLossTime"), value: formatDuration(s.longest_holding_losers) },
    { label: t("journal.kpi.loss.maxDrawdown"), value: formatMoney(-s.max_drawdown, { signed: true }), color: s.max_drawdown > 0 ? "var(--danger)" : undefined },
    { label: t("journal.kpi.loss.drawdownFrom"), value: formatDateTime(s.max_drawdown_from) },
    { label: t("journal.kpi.loss.drawdownTo"), value: formatDateTime(s.max_drawdown_to) },
  ];
}
