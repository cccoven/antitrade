import { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Plus, ScanSearch, Download, Search, ChevronLeft, ChevronRight, RefreshCw, X, NotebookPen, ClipboardPen, Eye, EyeOff } from "lucide-react";
import FlushPage from "../components/FlushPage";
import TradeForm from "../components/TradeForm";
import TradeList from "../components/TradeList";
import TradePlanForm from "../components/TradePlanForm";
import TradePlansPanel from "../components/TradePlansPanel";
import TradeImportDialog from "../components/TradeImportDialog";
import JournalStatsPanel from "./JournalStatsPage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  animatedLineTabClassName,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  journalFilterControlSizes,
  journalToolbarControlSizes,
} from "@/pages/journal-ui-config";
import { formatLocalDate } from "@/pages/daily-review-utils";
import {
  applyJournalSymbolDraft,
  buildJournalTradeQueryParams,
  journalLocalDateTimeToIso,
} from "@/pages/journal-filtering";
import { useToast } from "@/components/Toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  listTrades,
  deleteTrade,
  exportTrades,
  fetchTradeStats,
  type Trade, type TradePlan, type TradeStats,
} from "@/api/client";
import { readJournalState, writeJournalState } from "@/state/ui-storage";
import { useSelection } from "@/hooks/useSelection";
import { useJournalSettings } from "@/journal/journal-settings-context";
import BatchToolbar from "@/components/BatchToolbar";
import {
  batchDeleteTrades,
  batchAddTags,
  exportTradesSelected,
  type BatchTarget,
} from "@/api/client";
import { formatPct } from "./journal-stats/journal-stats-format";

const DIRECTION_OPTIONS = [
  { value: "all", key: "journal.allDirections" },
  { value: "long", key: "journal.long" },
  { value: "short", key: "journal.short" },
] as const;

const POSITION_STATUS_OPTIONS = [
  { value: "all", key: "journal.status.all" },
  { value: "open", key: "journal.status.open" },
  { value: "closed", key: "journal.status.closed" },
] as const;

export default function JournalPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user, loading: authLoading } = useAuth();
  const {
    amountsVisible,
    displayMoney,
    setAmountsVisible,
  } = useJournalSettings();
  const [activeView, setActiveView] = useState("trades");

  const filterInputClassName =
    journalFilterControlSizes.input === "sm"
      ? `h-8 w-[220px] pr-10 ${journalFilterControlSizes.inputPlaceholderClassName}`
      : `w-[220px] pr-10 ${journalFilterControlSizes.inputPlaceholderClassName}`;

  // Read persisted filter state
  const persisted = readJournalState({
    filterSymbol: "",
    filterDirection: "",
    filterPositionStatus: "",
    filterDateFrom: "",
    filterDateTo: "",
  });

  // Trade list state
  const [trades, setTrades] = useState<Trade[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [summary, setSummary] = useState<TradeStats | null>(null);
  const [openTradeCount, setOpenTradeCount] = useState(0);

  // Pagination state
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const [total, setTotal] = useState(0);

  // Refresh key — bump to re-fetch all data (trades + stats)
  const [refreshKey, setRefreshKey] = useState(0);

  // Filter state (persisted)
  const [filterSymbol, setFilterSymbol] = useState(persisted.filterSymbol);
  const [symbolDraft, setSymbolDraft] = useState(persisted.filterSymbol);
  const [filterDirection, setFilterDirection] = useState(
    persisted.filterDirection || "all"
  );
  const [filterPositionStatus, setFilterPositionStatus] = useState(
    persisted.filterPositionStatus || "all"
  );
  const [filterDateFrom, setFilterDateFrom] = useState(persisted.filterDateFrom);
  const [filterDateTo, setFilterDateTo] = useState(persisted.filterDateTo);

  // TradeForm drawer state
  const [formOpen, setFormOpen] = useState(false);
  const [editingTrade, setEditingTrade] = useState<Trade | null>(null);
  const [initialPlan, setInitialPlan] = useState<TradePlan | null>(null);
  const [planFormOpen, setPlanFormOpen] = useState(false);

  const [importOpen, setImportOpen] = useState(false);

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  // Batch selection state
  const selection = useSelection();
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);

  // Fetch trades
  const fetchTrades = useCallback(async () => {
    try {
      const params = buildJournalTradeQueryParams(
        filterSymbol,
        filterDirection,
        filterPositionStatus,
        filterDateFrom,
        filterDateTo,
        pageSize,
        page * pageSize,
      );
      const data = await listTrades(params);
      setTrades(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch {
      // Error toast handled by unwrapResponse
    } finally {
      setInitialLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterSymbol, filterDirection, filterPositionStatus, filterDateFrom, filterDateTo, page, refreshKey]);

  useEffect(() => {
    if (!user) return;
    fetchTrades();
  }, [fetchTrades, user]);

  useEffect(() => {
    let cancelled = false;
    if (!user) return;
    Promise.all([
      fetchTradeStats(),
      listTrades({ position_status: "open", limit: 1, offset: 0 }),
    ])
      .then(([stats, openTrades]) => {
        if (cancelled) return;
        setSummary(stats);
        setOpenTradeCount(openTrades.total);
      })
      .catch(() => {
        if (cancelled) return;
        setSummary(null);
        setOpenTradeCount(0);
      });
    return () => { cancelled = true; };
  }, [refreshKey, user]);

  // Persist filter state
  useEffect(() => {
    writeJournalState({
      filterSymbol,
      filterDirection: filterDirection === "all" ? "" : filterDirection,
      filterPositionStatus: filterPositionStatus === "all" ? "" : filterPositionStatus,
      filterDateFrom,
      filterDateTo,
    });
  }, [filterDateFrom, filterDateTo, filterDirection, filterPositionStatus, filterSymbol]);

  // Selection is scoped to a filter view — clear when filters change.
  useEffect(() => {
    selection.clear();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterSymbol, filterDirection, filterPositionStatus, filterDateFrom, filterDateTo]);

  // Handlers
  const handleNew = () => {
    setEditingTrade(null);
    setInitialPlan(null);
    setFormOpen(true);
  };

  const handleEdit = (trade: Trade) => {
    setEditingTrade(trade);
    setInitialPlan(null);
    setFormOpen(true);
  };

  const handleConvertPlan = (plan: TradePlan) => {
    setEditingTrade(null);
    setInitialPlan(plan);
    setFormOpen(true);
  };

  const handleSaved = () => {
    setActiveView("trades");
    setFormOpen(false);
    setEditingTrade(null);
    setInitialPlan(null);
    setRefreshKey((k) => k + 1);
    fetchTrades();
  };

  const handleDelete = async (tradeId: string) => {
    try {
      await deleteTrade(tradeId);
      showToast(t("journal.tradeDeleted"), "success");
      setRefreshKey((k) => k + 1);
      fetchTrades();
    } catch {
      // Error toast handled by unwrapResponse
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportTrades("csv");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "trades.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Error toast handled by unwrapResponse
    }
  };

  const buildBatchTarget = useCallback((): BatchTarget => {
    if (selection.allMatching) {
      return {
        select_all_matching: true,
        filter: {
          symbol: filterSymbol || undefined,
          direction: filterDirection !== "all" ? filterDirection : undefined,
          position_status: filterPositionStatus !== "all"
            ? filterPositionStatus as "open" | "closed"
            : undefined,
          date_from: filterDateFrom ? journalLocalDateTimeToIso(filterDateFrom) : undefined,
          date_to: filterDateTo ? journalLocalDateTimeToIso(filterDateTo) : undefined,
        },
      };
    }
    return { trade_ids: Array.from(selection.selectedIds) };
  }, [selection.allMatching, selection.selectedIds, filterSymbol, filterDirection, filterPositionStatus, filterDateFrom, filterDateTo]);

  const handleBatchDeleteConfirm = async () => {
    setBatchDeleteOpen(false);
    try {
      const { deleted } = await batchDeleteTrades(buildBatchTarget());
      const msg =
        deleted === 0
          ? t("journal.batch.exportEmpty")
          : t("journal.batch.deleteSuccess", { count: deleted });
      showToast(msg, "success");
      selection.clear();
      setPage(0);
      setRefreshKey((k) => k + 1);
      fetchTrades();
    } catch {
      // unwrapResponse already surfaces a toast
    }
  };

  const handleBatchTagConfirm = async (tags: string[]) => {
    try {
      const { updated } = await batchAddTags(buildBatchTarget(), tags);
      const msg =
        updated === 0
          ? t("journal.batch.exportEmpty")
          : t("journal.batch.tagSuccess", { count: updated });
      showToast(msg, "success");
      selection.clear();
      setRefreshKey((k) => k + 1);
      fetchTrades();
    } catch {
      // handled upstream
    }
  };

  const handleExportSelected = async () => {
    try {
      const blob = await exportTradesSelected(buildBatchTarget(), "csv");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "trades-selected.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // handled upstream
    }
  };

  // existingTags suggested from currently-loaded page
  const existingTagsSuggestion = useMemo(() => {
    const s = new Set<string>();
    for (const tr of trades) for (const tag of tr.tags) s.add(tag);
    return Array.from(s);
  }, [trades]);

  const selectedCount = selection.count(total);
  const normalizedSymbolDraft = applyJournalSymbolDraft(symbolDraft);
  const hasPendingSymbolFilter = normalizedSymbolDraft !== filterSymbol;
  const hasTimeFilter = Boolean(filterDateFrom || filterDateTo);

  const [refreshSpin, setRefreshSpin] = useState(false);
  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
    setRefreshSpin(true);
    setTimeout(() => setRefreshSpin(false), 600);
  };

  const handleApplySymbolFilter = useCallback(() => {
    setPage(0);
    setFilterSymbol(applyJournalSymbolDraft(symbolDraft));
  }, [symbolDraft]);
  const handleDirectionChange = useCallback((value: string) => {
    setPage(0);
    setFilterDirection(value);
  }, []);
  const handlePositionStatusChange = useCallback((value: string) => {
    setPage(0);
    setFilterPositionStatus(value);
  }, []);
  const handleDateFromChange = useCallback((value: string) => {
    setPage(0);
    setFilterDateFrom(value);
  }, []);
  const handleDateToChange = useCallback((value: string) => {
    setPage(0);
    setFilterDateTo(value);
  }, []);
  const handleClearTimeFilter = useCallback(() => {
    setFilterDateFrom("");
    setFilterDateTo("");
    setPage(0);
  }, []);

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  const toolbarBtnStyle = {
    fontSize: journalToolbarControlSizes.fontSize,
    fontWeight: journalToolbarControlSizes.fontWeight,
  };

  return (
    <>
    <TooltipProvider>
    <Tabs value={activeView} onValueChange={setActiveView} className="gap-0">
    <FlushPage
      contentClassName="pt-0"
      toolbar={
        <>
          <TabsList variant="line" className="h-7 gap-3 p-0">
            <TabsTrigger
              value="trades"
              style={toolbarBtnStyle}
              className={animatedLineTabClassName}
            >
              {t("journal.tab.trades")}
            </TabsTrigger>
            <TabsTrigger
              value="plans"
              style={toolbarBtnStyle}
              className={animatedLineTabClassName}
            >
              {t("journal.tab.plans")}
            </TabsTrigger>
            <TabsTrigger
              value="analytics"
              style={toolbarBtnStyle}
              className={animatedLineTabClassName}
            >
              {t("journal.tab.analytics")}
            </TabsTrigger>
          </TabsList>
          <span className="h-4 w-px shrink-0 bg-border" aria-hidden="true" />
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size={journalToolbarControlSizes.iconAction}
                  style={toolbarBtnStyle}
                  onClick={handleNew}
                  aria-label={t("journal.newTrade")}
                >
                  <Plus />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">{t("journal.newTrade")}</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size={journalToolbarControlSizes.iconAction}
                  variant="outline"
                  style={toolbarBtnStyle}
                  onClick={() => setPlanFormOpen(true)}
                  aria-label={t("tradePlan.new")}
                >
                  <ClipboardPen />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">{t("tradePlan.new")}</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size={journalToolbarControlSizes.iconAction}
                  variant="outline"
                  style={toolbarBtnStyle}
                  onClick={() => setImportOpen(true)}
                  aria-label={t("tradeImport.title")}
                >
                  <ScanSearch />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">{t("tradeImport.title")}</TooltipContent>
            </Tooltip>
          </div>
        </>
      }
      toolbarAside={
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size={journalToolbarControlSizes.iconAction}
                style={toolbarBtnStyle}
                onClick={() => setAmountsVisible(!amountsVisible)}
                aria-label={t(amountsVisible ? "journal.hideAmounts" : "journal.showAmounts")}
                aria-pressed={!amountsVisible}
              >
                {amountsVisible ? <Eye /> : <EyeOff />}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              {t(amountsVisible ? "journal.hideAmounts" : "journal.showAmounts")}
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size={journalToolbarControlSizes.iconAction}
                style={toolbarBtnStyle}
                onClick={() => navigate(`/journal/review?date=${formatLocalDate(new Date())}`)}
                aria-label={t("dailyReview.titleNav")}
              >
                <NotebookPen />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">{t("dailyReview.titleNav")}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size={journalToolbarControlSizes.iconAction}
                style={toolbarBtnStyle}
                onClick={handleRefresh}
                aria-label={t("journal.refresh")}
              >
                <RefreshCw className={refreshSpin ? "animate-spin" : ""} />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">{t("journal.refresh")}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size={journalToolbarControlSizes.iconAction}
                style={toolbarBtnStyle}
                onClick={handleExport}
                aria-label={t("journal.export")}
              >
                <Download />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">{t("journal.export")}</TooltipContent>
          </Tooltip>
        </div>
      }
    >
        <TabsContent value="trades" className="mt-0 flex flex-col gap-3 pt-3">
          {summary ? (
            <section className="grid overflow-hidden rounded-[var(--radius-data-panel)] border border-[var(--data-grid-line)] bg-[var(--data-panel-bg)] sm:grid-cols-2 xl:grid-cols-4">
              {[
                {
                  label: t("journal.kpi.totalPnl"),
                  value: displayMoney(summary.total_pnl, { signed: true }),
                  tone: summary.total_pnl > 0
                    ? "text-[var(--market-up)]"
                    : summary.total_pnl < 0
                      ? "text-[var(--market-down)]"
                      : "text-foreground",
                },
                {
                  label: t("journal.kpi.winRate"),
                  value: formatPct(summary.win_rate),
                  tone: "text-foreground",
                },
                {
                  label: t("journal.openPositions"),
                  value: String(openTradeCount),
                  tone: openTradeCount > 0 ? "text-[var(--market-info)]" : "text-foreground",
                },
                {
                  label: t("journal.tradeCount"),
                  value: String(summary.total_trades + openTradeCount),
                  tone: "text-foreground",
                },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="flex min-h-16 items-center justify-between gap-4 border-b border-[var(--data-grid-line)] px-4 last:border-b-0 sm:[&:nth-child(odd)]:border-r xl:border-b-0 xl:border-r xl:last:border-r-0"
                >
                  <span className="text-micro font-medium uppercase tracking-[0.1em] text-muted-foreground">
                    {metric.label}
                  </span>
                  <span className={`market-data-value text-subheading font-semibold ${metric.tone}`}>
                    {metric.value}
                  </span>
                </div>
              ))}
            </section>
          ) : null}

          {selectedCount > 0 && (
            <BatchToolbar
              selectedCount={selectedCount}
              totalMatching={total}
              selectedOnPage={trades.filter((tr) => selection.selectedIds.has(tr.id)).length}
              currentPageLen={trades.length}
              allMatching={selection.allMatching}
              existingTags={existingTagsSuggestion}
              onSelectAllMatching={selection.selectAllMatching}
              onClearSelection={selection.clear}
              onBatchDelete={() => setBatchDeleteOpen(true)}
              onBatchTagConfirm={handleBatchTagConfirm}
              onExportSelected={handleExportSelected}
            />
          )}

          <div className="scroll-mt-4">
            <Card className="gap-0 py-0">
              <CardContent className="flex flex-col gap-4 px-4 py-4">
                <div className="flex flex-wrap items-end gap-2">
                <div className="relative">
                  <Input
                    className={filterInputClassName}
                    style={{
                      fontSize: journalFilterControlSizes.valueFontSize,
                      fontWeight: journalFilterControlSizes.valueFontWeight,
                    }}
                    value={symbolDraft}
                    onChange={(e) => setSymbolDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleApplySymbolFilter();
                      }
                    }}
                    placeholder={t("journal.filterSymbol")}
                  />
                  <Button
                    type="button"
                    variant={hasPendingSymbolFilter ? "secondary" : "ghost"}
                    size={journalFilterControlSizes.searchAction}
                    className="absolute right-1 top-1/2 -translate-y-1/2"
                    onClick={handleApplySymbolFilter}
                    aria-label={t("journal.applyFilter")}
                    title={t("journal.applyFilter")}
                  >
                    <Search />
                  </Button>
                </div>
                <Select value={filterDirection} onValueChange={handleDirectionChange}>
                  <SelectTrigger
                    size={journalFilterControlSizes.select}
                    className={`w-[120px] ${journalFilterControlSizes.selectPlaceholderClassName}`}
                    style={{
                      fontSize: journalFilterControlSizes.valueFontSize,
                      fontWeight: journalFilterControlSizes.valueFontWeight,
                    }}
                  >
                    <SelectValue placeholder={t("journal.allDirections")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {DIRECTION_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {t(opt.key)}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <Select value={filterPositionStatus} onValueChange={handlePositionStatusChange}>
                  <SelectTrigger
                    size={journalFilterControlSizes.select}
                    className={`w-[120px] ${journalFilterControlSizes.selectPlaceholderClassName}`}
                    style={{
                      fontSize: journalFilterControlSizes.valueFontSize,
                      fontWeight: journalFilterControlSizes.valueFontWeight,
                    }}
                  >
                    <SelectValue placeholder={t("journal.status.all")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {POSITION_STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {t(option.key)}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <DateTimePicker
                  value={filterDateFrom}
                  onChange={handleDateFromChange}
                  placeholder={t("journal.from")}
                  className="w-[188px] justify-start"
                  buttonSize={journalFilterControlSizes.dateTimeButton}
                  buttonStyle={{
                    fontSize: journalFilterControlSizes.dateTimeValueFontSize,
                    fontWeight: journalFilterControlSizes.dateTimeValueFontWeight,
                  }}
                  placeholderStyle={{
                    fontSize: journalFilterControlSizes.dateTimePlaceholderFontSize,
                  }}
                  timeInputClassName={journalFilterControlSizes.dateTimeTimeInputClassName}
                  timeInputStyle={{
                    fontSize: journalFilterControlSizes.dateTimeValueFontSize,
                    fontWeight: journalFilterControlSizes.dateTimeValueFontWeight,
                  }}
                />
                <DateTimePicker
                  value={filterDateTo}
                  onChange={handleDateToChange}
                  placeholder={t("journal.to")}
                  className="w-[188px] justify-start"
                  buttonSize={journalFilterControlSizes.dateTimeButton}
                  buttonStyle={{
                    fontSize: journalFilterControlSizes.dateTimeValueFontSize,
                    fontWeight: journalFilterControlSizes.dateTimeValueFontWeight,
                  }}
                  placeholderStyle={{
                    fontSize: journalFilterControlSizes.dateTimePlaceholderFontSize,
                  }}
                  timeInputClassName={journalFilterControlSizes.dateTimeTimeInputClassName}
                  timeInputStyle={{
                    fontSize: journalFilterControlSizes.dateTimeValueFontSize,
                    fontWeight: journalFilterControlSizes.dateTimeValueFontWeight,
                  }}
                />
                {hasTimeFilter && (
                  <Button
                    type="button"
                    variant="ghost"
                    size={journalFilterControlSizes.clearTimeAction}
                    className="mb-0.5"
                    onClick={handleClearTimeFilter}
                    aria-label={t("journal.clearTimeFilter")}
                    title={t("journal.clearTimeFilter")}
                  >
                    <X />
                  </Button>
                )}
                </div>

                {initialLoading ? (
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ) : (
                  <div>
                    <TradeList
                      trades={trades}
                      onEdit={handleEdit}
                      onDelete={(id) => setDeleteTarget(id)}
                      selection={selection}
                    />
                    {total > 0 && (
                      <div className="flex items-center justify-between pt-2">
                        <span className="text-caption text-muted-foreground">
                          {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} / {total}
                        </span>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="outline"
                            size="icon-sm"
                            disabled={page === 0}
                            onClick={() => setPage((p) => p - 1)}
                            aria-label={t("journal.prevPage")}
                          >
                            <ChevronLeft />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon-sm"
                            disabled={(page + 1) * pageSize >= total}
                            onClick={() => setPage((p) => p + 1)}
                            aria-label={t("journal.nextPage")}
                          >
                            <ChevronRight />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="plans" className="mt-0 pt-3">
          <TradePlansPanel
            refreshKey={refreshKey}
            onConvert={handleConvertPlan}
            showEmpty
          />
        </TabsContent>

        <TabsContent value="analytics" className="mt-0">
          <JournalStatsPanel refreshKey={refreshKey} />
        </TabsContent>
    </FlushPage>
    </Tabs>
    </TooltipProvider>

      {/* Drawers and dialogs */}
      <TradeForm
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditingTrade(null);
          setInitialPlan(null);
        }}
        onSaved={handleSaved}
        trade={editingTrade}
        initialPlan={initialPlan}
      />
      <TradePlanForm
        open={planFormOpen}
        onClose={() => setPlanFormOpen(false)}
        onSaved={() => {
          setRefreshKey((key) => key + 1);
          setActiveView("plans");
        }}
      />
      <TradeImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => {
          setImportOpen(false);
          setRefreshKey((k) => k + 1);
          fetchTrades();
        }}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title={t("journal.confirmDelete")}
        onConfirm={() => {
          if (deleteTarget) handleDelete(deleteTarget);
          setDeleteTarget(null);
        }}
      />
      <ConfirmDialog
        open={batchDeleteOpen}
        onOpenChange={setBatchDeleteOpen}
        title={t("journal.batch.confirmDeleteTitle", { count: selectedCount })}
        description={
          selection.allMatching
            ? t("journal.batch.confirmDeleteCrossPage", { count: selectedCount })
            : t("journal.batch.confirmDeleteBody")
        }
        onConfirm={handleBatchDeleteConfirm}
      />
    </>
  );
}
