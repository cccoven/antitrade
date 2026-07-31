import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  createPortfolio,
  createPortfolioCategory,
  createPortfolioEntry,
  deletePortfolio,
  deletePortfolioEntry,
  exportPortfolio,
  getPortfolioSummary,
  importPortfolio,
  listPortfolioCategories,
  listPortfolioEntries,
  listPortfolios,
  updatePortfolio,
  updatePortfolioEntry,
  type CreatePortfolioEntryRequest,
  type Portfolio,
  type PortfolioCategory,
  type PortfolioEntry,
  type PortfolioEntryFilter,
  type PortfolioSummary,
} from "@/api/client";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  Download,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  Upload,
  Search,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import ReactECharts from "echarts-for-react";
import {
  portfolioFilterControlSizes,
  portfolioInlineTagClassName,
  portfolioTableControlSizes,
  portfolioToolbarControlSizes,
} from "./portfolio-ui-config";
import PortfolioForm from "@/components/PortfolioForm";
import PortfolioDialog from "@/components/PortfolioDialog";
import FlushPage from "@/components/FlushPage";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { showToast } from "@/components/Toast";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import {
  readActivePortfolioId,
  writeActivePortfolioId,
} from "@/state/ui-storage";

const toolbarBtnStyle = {
  fontSize: portfolioToolbarControlSizes.fontSize,
  fontWeight: portfolioToolbarControlSizes.fontWeight,
} as const;

const filterInputStyle = {
  fontSize: portfolioFilterControlSizes.fontSize,
  fontWeight: portfolioFilterControlSizes.fontWeight,
} as const;

interface SummaryCardProps {
  label: string;
  value: string;
  valueStyle?: React.CSSProperties;
}

function SummaryCard({ label, value, valueStyle }: SummaryCardProps) {
  return (
    <Card className="gap-2 py-4 shadow-none">
      <CardHeader className="px-4 pb-0">
        <CardDescription className="text-caption text-muted-foreground">
          {label}
        </CardDescription>
      </CardHeader>
      <CardContent className="px-4 pt-0">
        <div
          className="text-heading font-semibold leading-none tabular-nums"
          style={valueStyle}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

const NEW_PORTFOLIO_SENTINEL = "__new__";

export default function PortfolioPage() {
  const { t } = useTranslation();
  const { user, loading: authLoading } = useAuth();

  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [categories, setCategories] = useState<PortfolioCategory[]>([]);
  const [entries, setEntries] = useState<PortfolioEntry[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [filter, setFilter] = useState<PortfolioEntryFilter>({});

  const [portfolioDialogOpen, setPortfolioDialogOpen] = useState(false);
  const [portfolioDialogMode, setPortfolioDialogMode] = useState<"create" | "edit">("create");
  const [entryFormOpen, setEntryFormOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<PortfolioEntry | null>(null);
  const [entryDeleteTarget, setEntryDeleteTarget] = useState<PortfolioEntry | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activePortfolio = useMemo(
    () => portfolios.find((p) => p.id === activeId) ?? null,
    [portfolios, activeId],
  );

  const loadShell = useCallback(async () => {
    const [pRes, cRes] = await Promise.all([
      listPortfolios(),
      listPortfolioCategories(),
    ]);
    setPortfolios(pRes.items);
    setCategories(cRes.items);

    if (pRes.items.length === 0) {
      setActiveId(null);
      writeActivePortfolioId(null);
      return;
    }

    const stored = readActivePortfolioId();
    const resolved =
      (stored && pRes.items.some((p) => p.id === stored) ? stored : null) ??
      pRes.items[0].id;
    setActiveId(resolved);
    writeActivePortfolioId(resolved);
  }, []);

  useEffect(() => {
    if (!user) return;
    void loadShell();
  }, [user, loadShell]);

  const loadActivePortfolioData = useCallback(async () => {
    if (!activeId) {
      setEntries([]);
      setSummary(null);
      return;
    }
    const [e, s] = await Promise.all([
      listPortfolioEntries(activeId, filter),
      getPortfolioSummary(activeId),
    ]);
    setEntries(e.items);
    setSummary(s);
  }, [activeId, filter]);

  useEffect(() => {
    void loadActivePortfolioData();
  }, [loadActivePortfolioData]);

  const handleSelectPortfolio = (value: string) => {
    if (value === NEW_PORTFOLIO_SENTINEL) {
      setPortfolioDialogMode("create");
      setPortfolioDialogOpen(true);
      return;
    }
    setActiveId(value);
    writeActivePortfolioId(value);
    setFilter({});
  };

  const handleCreatePortfolio = async (payload: { name: string; currency: string }) => {
    const created = await createPortfolio(payload);
    await loadShell();
    setActiveId(created.id);
    writeActivePortfolioId(created.id);
    setFilter({});
  };

  const handleUpdatePortfolio = async (payload: { name: string; currency: string }) => {
    if (!activePortfolio) return;
    await updatePortfolio(activePortfolio.id, payload);
    await loadShell();
  };

  const handleDeletePortfolio = async () => {
    if (!activePortfolio) return;
    await deletePortfolio(activePortfolio.id);
    writeActivePortfolioId(null);
    setActiveId(null);
    await loadShell();
  };

  const handleSaveEntry = async (payload: CreatePortfolioEntryRequest) => {
    if (!activeId) return;
    if (editingEntry) {
      await updatePortfolioEntry(editingEntry.id, payload);
    } else {
      await createPortfolioEntry(activeId, payload);
    }
    await Promise.all([loadShell(), loadActivePortfolioData()]);
  };

  const handleCreateCategory = async (name: string, kind: "asset" | "liability") => {
    await createPortfolioCategory(name, kind);
    const c = await listPortfolioCategories();
    setCategories(c.items);
  };

  const handleDeleteEntry = async () => {
    if (!entryDeleteTarget) return;
    await deletePortfolioEntry(entryDeleteTarget.id);
    setEntryDeleteTarget(null);
    await Promise.all([loadShell(), loadActivePortfolioData()]);
  };

  const handleExport = async () => {
    if (!activeId) return;
    const blob = await exportPortfolio(activeId);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `portfolio-${activePortfolio?.name ?? activeId}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleImport = async (file: File) => {
    if (!activeId) return;
    const result = await importPortfolio(activeId, file);
    showToast(
      t("portfolio.importSuccess", {
        inserted: result.inserted,
        skipped: result.skipped,
      }),
    );
    await Promise.all([loadShell(), loadActivePortfolioData()]);
  };

  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 2 });

  const fmtCompact = (n: number) => {
    const abs = Math.abs(n);
    if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  const buildChart = useCallback(
    (data: { name: string; value: number; isLiability?: boolean; count: number }[]) => {
      if (!data.length) return null;
      const cs = getComputedStyle(document.documentElement);
      const textColor = cs.getPropertyValue("--muted-foreground").trim() || "#888";
      const borderColor = cs.getPropertyValue("--border").trim();
      const accentColor = cs.getPropertyValue("--primary").trim() || "#b88352";
      const dangerColor = cs.getPropertyValue("--danger").trim() || "#b85b5b";
      const panelBg = cs.getPropertyValue("--popover").trim() || "#1f1f1f";
      const primaryText = cs.getPropertyValue("--foreground").trim() || "#e7e7e7";

      const sorted = [...data].sort((a, b) => b.value - a.value);
      const cur = activePortfolio?.currency ?? "";

      return {
        animationDuration: 200,
        grid: { left: 8, right: 96, top: 8, bottom: 8, containLabel: true },
        tooltip: {
          trigger: "axis" as const,
          axisPointer: { type: "shadow" as const },
          backgroundColor: panelBg,
          borderColor,
          textStyle: { color: primaryText, fontSize: 12 },
          formatter: (params: unknown) => {
            const arr = params as Array<{ dataIndex: number }>;
            const row = sorted[arr[0]?.dataIndex ?? 0];
            return [
              `<div style="font-weight:600;margin-bottom:4px">${row.name}</div>`,
              `${cur} ${row.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
              `#: ${row.count}`,
            ].join("<br/>");
          },
        },
        xAxis: {
          type: "value" as const,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: textColor, fontSize: 10, formatter: (v: number) => fmtCompact(v) },
          splitLine: { lineStyle: { color: borderColor, type: "dashed" as const } },
        },
        yAxis: {
          type: "category" as const,
          data: sorted.map((d) => d.name),
          axisLine: { lineStyle: { color: borderColor } },
          axisTick: { show: false },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "bar" as const,
            data: sorted.map((d) => ({
              value: d.value,
              itemStyle: {
                color: d.isLiability ? dangerColor : accentColor,
                borderRadius: [0, 4, 4, 0],
              },
            })),
            label: {
              show: true,
              position: "right" as const,
              formatter: (p: { value: number }) => fmtCompact(p.value),
              color: textColor,
              fontSize: 10,
            },
            barMaxWidth: 22,
          },
        ],
      };
    },
    [activePortfolio?.currency],
  );

  const categoryChart = useMemo(() => {
    return buildChart(
      (summary?.by_category ?? []).map((g) => ({
        name: g.name,
        value: g.total,
        isLiability: g.kind === "liability",
        count: g.count,
      })),
    );
  }, [summary, buildChart]);

  const platformChart = useMemo(() => {
    return buildChart(
      (summary?.by_platform ?? []).map((g) => ({
        name: g.name || "—",
        value: g.total,
        count: g.count,
      })),
    );
  }, [summary, buildChart]);

  const chartHeight = (n: number) => Math.max(160, n * 32 + 24);

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  const currency = activePortfolio?.currency ?? "";

  // No portfolios — onboarding empty state
  if (portfolios.length === 0 && activeId === null) {
    return (
      <FlushPage toolbar={<span />} contentClassName="pt-6">
        <Empty className="min-h-[260px] border border-dashed border-border bg-[var(--chip-bg)] p-8">
            <EmptyHeader>
              <EmptyTitle className="text-subheading text-foreground">
                {t("portfolio.noPortfoliosTitle")}
              </EmptyTitle>
              <EmptyDescription className="text-caption text-muted-foreground">
                {t("portfolio.noPortfoliosDescription")}
              </EmptyDescription>
            </EmptyHeader>
            <Button
              size={portfolioToolbarControlSizes.primaryAction}
              style={toolbarBtnStyle}
              onClick={() => {
                setPortfolioDialogMode("create");
                setPortfolioDialogOpen(true);
              }}
              className="mt-3"
            >
              <Plus data-icon="inline-start" />
              {t("portfolio.noPortfoliosCta")}
            </Button>
          </Empty>
        <PortfolioDialog
          open={portfolioDialogOpen}
          onOpenChange={setPortfolioDialogOpen}
          mode="create"
          onSubmit={handleCreatePortfolio}
        />
      </FlushPage>
    );
  }

  return (
    <>
    <FlushPage
      contentClassName="pt-3"
      toolbarAside={
        <div className="flex items-center gap-2">
          <TooltipIconButton
            label={t("portfolio.export")}
            variant="outline"
            size={portfolioToolbarControlSizes.iconAction}
            onClick={handleExport}
            disabled={!activeId}
          >
            <Download />
          </TooltipIconButton>
          <TooltipIconButton
            label={t("portfolio.import")}
            variant="outline"
            size={portfolioToolbarControlSizes.iconAction}
            onClick={() => fileInputRef.current?.click()}
            disabled={!activeId}
          >
            <Upload />
          </TooltipIconButton>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(ev) => {
              const file = ev.target.files?.[0];
              if (file) void handleImport(file);
              ev.target.value = "";
            }}
          />
        </div>
      }
      toolbar={
        <>
          <div className="flex items-center gap-2">
            <Select value={activeId ?? ""} onValueChange={handleSelectPortfolio}>
              <SelectTrigger
                size={portfolioFilterControlSizes.select as "sm"}
                style={filterInputStyle}
                className="min-w-[200px]"
              >
                <SelectValue placeholder={t("portfolio.switcher.placeholder")} />
              </SelectTrigger>
              <SelectContent>
                {portfolios.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    <span className="flex items-center justify-between gap-6 min-w-[180px]">
                      <span>{p.name}</span>
                      <span className="text-caption text-muted-foreground">
                        {p.currency} · {t("portfolio.entryCount", { count: p.entry_count })}
                      </span>
                    </span>
                  </SelectItem>
                ))}
                <SelectSeparator />
                <SelectItem value={NEW_PORTFOLIO_SENTINEL}>
                  <span className="flex items-center gap-2">
                    <Plus className="size-[var(--icon-xs)]" />
                    {t("portfolio.newPortfolio")}
                  </span>
                </SelectItem>
              </SelectContent>
            </Select>
            {activePortfolio && (
              <TooltipIconButton
                label={t("portfolio.editPortfolio")}
                variant="ghost"
                size={portfolioToolbarControlSizes.iconAction}
                onClick={() => {
                  setPortfolioDialogMode("edit");
                  setPortfolioDialogOpen(true);
                }}
              >
                <Pencil />
              </TooltipIconButton>
            )}
          </div>
          <TooltipIconButton
            label={t("portfolio.addEntry")}
            size={portfolioToolbarControlSizes.iconAction}
            style={toolbarBtnStyle}
            onClick={() => {
              setEditingEntry(null);
              setEntryFormOpen(true);
            }}
            disabled={!activeId}
          >
            <Plus />
          </TooltipIconButton>
        </>
      }
    >
        {/* Summary cards */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <SummaryCard
            label={t("portfolio.totalAssets")}
            value={summary ? `${currency} ${fmt(summary.totals.assets)}` : "—"}
          />
          <SummaryCard
            label={t("portfolio.totalLiabilities")}
            value={summary ? `${currency} ${fmt(summary.totals.liabilities)}` : "—"}
            valueStyle={
              summary && summary.totals.liabilities > 0
                ? { color: "var(--danger)" }
                : undefined
            }
          />
          <SummaryCard
            label={t("portfolio.netWorth")}
            value={summary ? `${currency} ${fmt(summary.totals.net_worth)}` : "—"}
          />
        </section>

        {/* Breakdown tabs */}
        <section>
          <Tabs defaultValue="category">
            <TabsList>
              <TabsTrigger
                value="category"
                style={{ fontSize: "var(--font-ui)", fontWeight: 400 }}
              >
                {t("portfolio.byCategory")}
              </TabsTrigger>
              <TabsTrigger
                value="platform"
                style={{ fontSize: "var(--font-ui)", fontWeight: 400 }}
              >
                {t("portfolio.byPlatform")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="category" className="pt-3">
              {categoryChart ? (
                <ReactECharts
                  option={categoryChart}
                  style={{ height: chartHeight(summary?.by_category.length ?? 0) }}
                  opts={{ renderer: "svg" }}
                  notMerge
                />
              ) : (
                <div className="text-caption text-muted-foreground py-6 text-center">—</div>
              )}
            </TabsContent>
            <TabsContent value="platform" className="pt-3">
              {platformChart ? (
                <ReactECharts
                  option={platformChart}
                  style={{ height: chartHeight(summary?.by_platform.length ?? 0) }}
                  opts={{ renderer: "svg" }}
                  notMerge
                />
              ) : (
                <div className="text-caption text-muted-foreground py-6 text-center">—</div>
              )}
            </TabsContent>
          </Tabs>
        </section>

        {/* Filter strip */}
        <section className="flex flex-wrap items-center gap-2">
          <Select
            value={filter.category ?? "__all"}
            onValueChange={(v) =>
              setFilter({ ...filter, category: v === "__all" ? undefined : v })
            }
          >
            <SelectTrigger
              size={portfolioFilterControlSizes.select as "sm"}
              style={filterInputStyle}
              className={`w-[140px] ${portfolioFilterControlSizes.selectPlaceholderClassName}`}
            >
              <SelectValue placeholder={t("portfolio.filter.category")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">{t("portfolio.filter.all")}</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c.id} value={c.name}>
                  {c.name}
                  {c.kind === "liability" ? ` · ${t("portfolio.liability")}` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={filter.platform ?? ""}
            onChange={(e) =>
              setFilter({ ...filter, platform: e.target.value || undefined })
            }
            placeholder={t("portfolio.filter.platform")}
            className={`h-8 w-[140px] ${portfolioFilterControlSizes.inputPlaceholderClassName}`}
            style={filterInputStyle}
          />
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-[var(--icon-xs)] text-muted-foreground" />
            <Input
              value={filter.search ?? ""}
              onChange={(e) =>
                setFilter({ ...filter, search: e.target.value || undefined })
              }
              placeholder={t("portfolio.filter.search")}
              className={`h-8 w-[220px] pl-8 ${portfolioFilterControlSizes.inputPlaceholderClassName}`}
              style={filterInputStyle}
            />
          </div>
        </section>

        {/* Entry list */}
        <section>
          {entries.length === 0 ? (
            <Empty className="min-h-[220px] border border-dashed border-border bg-[var(--chip-bg)] p-8">
              <EmptyHeader>
                <EmptyTitle className="text-subheading text-foreground">
                  {t("portfolio.emptyTitle")}
                </EmptyTitle>
                <EmptyDescription className="text-caption text-muted-foreground">
                  {t("portfolio.emptyDescription")}
                </EmptyDescription>
              </EmptyHeader>
              <Button
                size={portfolioToolbarControlSizes.primaryAction}
                style={toolbarBtnStyle}
                onClick={() => {
                  setEditingEntry(null);
                  setEntryFormOpen(true);
                }}
                className="mt-3"
                disabled={!activeId}
              >
                <Plus data-icon="inline-start" />
                {t("portfolio.emptyCta")}
              </Button>
            </Empty>
          ) : (
            <Table>
              <TableHeader className="[&_tr]:border-b-0">
                <TableRow>
                  <TableHead className={portfolioTableControlSizes.headerTextClassName}>
                    {t("portfolio.name")}
                  </TableHead>
                  <TableHead className={portfolioTableControlSizes.headerTextClassName}>
                    {t("portfolio.category")}
                  </TableHead>
                  <TableHead className={portfolioTableControlSizes.headerTextClassName}>
                    {t("portfolio.platform")}
                  </TableHead>
                  <TableHead
                    className={`text-right ${portfolioTableControlSizes.headerTextClassName}`}
                  >
                    {t("portfolio.amountHeader", { currency })}
                  </TableHead>
                  <TableHead className="w-[40px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((e) => {
                  const cat = categories.find((c) => c.name === e.category);
                  const isLiability = cat?.kind === "liability";
                  return (
                    <TableRow key={e.id}>
                      <TableCell className="text-ui">{e.name}</TableCell>
                      <TableCell className="text-ui">
                        {e.category}
                        {isLiability && (
                          <span className={portfolioInlineTagClassName}>
                            · {t("portfolio.liability")}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-ui">
                        {e.platform || (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell
                        className={`text-right text-ui tabular-nums ${
                          isLiability ? "text-[var(--danger)]" : ""
                        }`}
                      >
                        {e.amount.toLocaleString(undefined, {
                          maximumFractionDigits: 8,
                        })}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size={portfolioTableControlSizes.rowAction as "icon-xs"}
                              aria-label={t("portfolio.actions")}
                            >
                              <MoreHorizontal />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onSelect={() => {
                                setEditingEntry(e);
                                setEntryFormOpen(true);
                              }}
                            >
                              <Pencil /> {t("portfolio.editEntry")}
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => setEntryDeleteTarget(e)}>
                              <Trash2 /> {t("portfolio.deleteEntry")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </section>
    </FlushPage>

      <PortfolioDialog
        open={portfolioDialogOpen}
        onOpenChange={setPortfolioDialogOpen}
        mode={portfolioDialogMode}
        portfolio={portfolioDialogMode === "edit" ? activePortfolio : null}
        onSubmit={
          portfolioDialogMode === "create" ? handleCreatePortfolio : handleUpdatePortfolio
        }
        onDelete={portfolioDialogMode === "edit" ? handleDeletePortfolio : undefined}
      />

      <PortfolioForm
        open={entryFormOpen}
        onOpenChange={setEntryFormOpen}
        entry={editingEntry}
        categories={categories}
        onSubmit={handleSaveEntry}
        onCreateCategory={handleCreateCategory}
      />

      <ConfirmDialog
        open={entryDeleteTarget !== null}
        onOpenChange={(o) => !o && setEntryDeleteTarget(null)}
        title={t("portfolio.confirmDeleteTitle")}
        description={t("portfolio.confirmDeleteBody")}
        confirmLabel={t("portfolio.deleteEntry")}
        onConfirm={handleDeleteEntry}
      />

    </>
  );
}
