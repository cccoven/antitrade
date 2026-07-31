import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Plus,
  Play,
  Save,
  Trash2,
  X,
  Loader2,
  ChevronDown,
} from "lucide-react";
import FlushPage from "@/components/FlushPage";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  animatedLineTabClassName,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import { useToast } from "@/components/Toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { backtestControlSizes } from "@/pages/backtest-ui-config";
import BacktestHistoryPanel from "@/pages/BacktestHistoryPanel";
import {
  listStrategies,
  createStrategy,
  updateStrategy,
  deleteStrategy as deleteStrategyApi,
  createBacktestRun,
  createOptimizationRun,
  createValidationRun,
  createWalkForwardRun,
  listBacktestRuns,
  getBacktestRun,
  rerunBacktest,
  deleteBacktestRun,
  searchMarketInstruments,
  type Strategy,
  type StrategyConfig,
  type StrategyCondition,
  type StrategyConditionGroup,
  type BacktestRun,
  type MarketInstrumentMatch,
} from "@/api/client";

// ── Constants ────────────────────────────────────────────

const DEFAULT_CONFIG: StrategyConfig = {
  symbol: "XAUUSD",
  interval: "60",
  direction: "long",
  entry_groups_operator: "or",
  entry_groups: [],
  exit_groups_operator: "or",
  exit_groups: [],
  stop_loss_pct: null,
  take_profit_pct: null,
  trailing_stop_pct: null,
  breakeven_trigger_pct: null,
  max_holding_bars: null,
  lookback_months: 3,
  initial_cash: 100_000,
  position_size: 1,
  commission_bps: 0,
  spread_bps: 0,
};

const INTERVAL_OPTIONS = [
  { value: "1", label: "1m" },
  { value: "5", label: "5m" },
  { value: "15", label: "15m" },
  { value: "60", label: "1h" },
  { value: "240", label: "4h" },
  { value: "D", label: "1D" },
] as const;

const INDICATOR_OPTIONS = [
  "price",
  "ema",
  "sma",
  "rsi",
  "macd",
  "bollinger",
  "atr",
  "value",
] as const;

const OPERATOR_OPTIONS = ["gt", "lt", "cross_above", "cross_below"] as const;

const INDICATORS_WITH_PERIOD = new Set(["ema", "sma", "rsi", "atr"]);
const INDICATORS_WITH_FIELD: Record<string, string[]> = {
  macd: ["main", "signal"],
  bollinger: ["upper", "middle", "lower"],
  price: ["close", "open", "high", "low"],
};

const LOOKBACK_OPTIONS = [1, 3, 6, 12] as const;
const HISTORY_PAGE_SIZE = 20;

const PRESET_MARKET_MATCHES: MarketInstrumentMatch[] = [
  {
    series_id: "series:spot:xau-usd:consolidated",
    symbol: "XAU/USD",
    name: "Gold Spot / U.S. Dollar",
    asset_class: "spot",
    venue: null,
    series_kind: "consolidated",
  },
  {
    series_id: "series:spot:eur-usd:consolidated",
    symbol: "EUR/USD",
    name: "Euro / U.S. Dollar",
    asset_class: "spot",
    venue: null,
    series_kind: "consolidated",
  },
  {
    series_id: "series:spot:gbp-usd:consolidated",
    symbol: "GBP/USD",
    name: "British Pound / U.S. Dollar",
    asset_class: "spot",
    venue: null,
    series_kind: "consolidated",
  },
  {
    series_id: "series:spot:usd-jpy:consolidated",
    symbol: "USD/JPY",
    name: "U.S. Dollar / Japanese Yen",
    asset_class: "spot",
    venue: null,
    series_kind: "consolidated",
  },
  {
    series_id: "series:crypto:btc-usd:consolidated",
    symbol: "BTC/USD",
    name: "Bitcoin / U.S. Dollar",
    asset_class: "crypto",
    venue: null,
    series_kind: "consolidated",
  },
  {
    series_id: "series:crypto:eth-usd:consolidated",
    symbol: "ETH/USD",
    name: "Ethereum / U.S. Dollar",
    asset_class: "crypto",
    venue: null,
    series_kind: "consolidated",
  },
  {
    series_id: "series:futures:nq:front",
    symbol: "NQ",
    name: "E-mini Nasdaq-100 Futures Continuous",
    asset_class: "futures",
    venue: "CME_MINI",
    series_kind: "continuous_future",
  },
  {
    series_id: "series:futures:es:front",
    symbol: "ES",
    name: "E-mini S&P 500 Futures Continuous",
    asset_class: "futures",
    venue: "CME_MINI",
    series_kind: "continuous_future",
  },
  {
    series_id: "series:futures:gc:front",
    symbol: "GC",
    name: "Gold Futures Continuous",
    asset_class: "futures",
    venue: "COMEX",
    series_kind: "continuous_future",
  },
  {
    series_id: "series:equity:aapl:xnas",
    symbol: "AAPL",
    name: "Apple Inc.",
    asset_class: "equity",
    venue: "XNAS",
    series_kind: "listing",
  },
  {
    series_id: "series:equity:tsla:xnas",
    symbol: "TSLA",
    name: "Tesla, Inc.",
    asset_class: "equity",
    venue: "XNAS",
    series_kind: "listing",
  },
  {
    series_id: "series:index:spx500:consolidated",
    symbol: "SPX500",
    name: "S&P 500 Index",
    asset_class: "index",
    venue: null,
    series_kind: "consolidated",
  },
];

const OPTIMIZATION_PARAMETERS = [
  "stop_loss_pct",
  "take_profit_pct",
  "trailing_stop_pct",
  "breakeven_trigger_pct",
  "max_holding_bars",
  "position_size",
] as const;

type OptimizationParameter = (typeof OPTIMIZATION_PARAMETERS)[number];

type OptimizationGridDraft = {
  id: number;
  parameter: OptimizationParameter;
  min: number;
  max: number;
  step: number;
};

// ── Helpers ──────────────────────────────────────────────

function makeDefaultCondition(): StrategyCondition {
  return {
    left: { type: "price", field: "close" },
    operator: "gt",
    right: { type: "ema", params: { period: 20 } },
  };
}

function parameterValues(min: number, max: number, step: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || !Number.isFinite(step)) {
    return [];
  }
  if (step <= 0 || max < min) return [];
  const values: number[] = [];
  for (let value = min; value <= max + step / 1000; value += step) {
    values.push(Number(value.toFixed(8)));
    if (values.length > 200) break;
  }
  return values;
}

function nextOptimizationParameter(
  grids: OptimizationGridDraft[],
): OptimizationParameter | null {
  return (
    OPTIMIZATION_PARAMETERS.find(
      (parameter) => !grids.some((grid) => grid.parameter === parameter),
    ) ?? null
  );
}

// ── ConditionRow ─────────────────────────────────────────

function ConditionSideEditor({
  side,
  onChange,
  t,
}: {
  side: StrategyCondition["left"];
  onChange: (s: StrategyCondition["left"]) => void;
  t: (key: string) => string;
}) {
  const indicatorType = side.type;
  const needsPeriod = INDICATORS_WITH_PERIOD.has(indicatorType);
  const fields = INDICATORS_WITH_FIELD[indicatorType];
  const isValue = indicatorType === "value";

  return (
    <div className="flex items-center gap-1.5">
      <Select
        value={indicatorType}
        onValueChange={(val) => {
          const next: StrategyCondition["left"] = { type: val };
          if (INDICATORS_WITH_PERIOD.has(val)) {
            next.params = { period: 20 };
          }
          if (INDICATORS_WITH_FIELD[val]) {
            next.field = INDICATORS_WITH_FIELD[val][0];
          }
          if (val === "value") {
            (next as StrategyCondition["right"]).value = 0;
          }
          onChange(next);
        }}
      >
        <SelectTrigger size="sm" className="w-[100px]" style={{ fontSize: "var(--font-ui)" }}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {INDICATOR_OPTIONS.map((ind) => (
              <SelectItem key={ind} value={ind}>
                {t(`backtest.indicator.${ind}`)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>

      {needsPeriod && (
        <Input
          type="number"
          className="h-8 w-[60px]"
          style={{ fontSize: "var(--font-ui)" }}
          value={side.params?.period ?? 20}
          onChange={(e) =>
            onChange({
              ...side,
              params: { ...side.params, period: Number(e.target.value) || 20 },
            })
          }
        />
      )}

      {fields && (
        <Select
          value={side.field ?? fields[0]}
          onValueChange={(val) => onChange({ ...side, field: val })}
        >
          <SelectTrigger size="sm" className="w-[90px]" style={{ fontSize: "var(--font-ui)" }}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {fields.map((f) => (
                <SelectItem key={f} value={f}>
                  {t(`backtest.field.${f}`)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      )}

      {isValue && (
        <Input
          type="number"
          className="h-8 w-[80px]"
          style={{ fontSize: "var(--font-ui)" }}
          value={(side as StrategyCondition["right"]).value ?? 0}
          onChange={(e) =>
            onChange({ ...side, value: Number(e.target.value) || 0 } as StrategyCondition["left"])
          }
        />
      )}
    </div>
  );
}

function ConditionRow({
  condition,
  onChange,
  onRemove,
  t,
}: {
  condition: StrategyCondition;
  onChange: (c: StrategyCondition) => void;
  onRemove: () => void;
  t: (key: string) => string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/15 p-2">
      <ConditionSideEditor
        side={condition.left}
        onChange={(left) => onChange({ ...condition, left })}
        t={t}
      />

      <Select
        value={condition.operator}
        onValueChange={(op) => onChange({ ...condition, operator: op })}
      >
        <SelectTrigger size="sm" className="w-[110px]" style={{ fontSize: "var(--font-ui)" }}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {OPERATOR_OPTIONS.map((op) => (
              <SelectItem key={op} value={op}>
                {t(`backtest.operator.${op}`)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>

      <ConditionSideEditor
        side={condition.right}
        onChange={(right) => onChange({ ...condition, right })}
        t={t}
      />

      <TooltipIconButton
        label={t("common.delete")}
        variant="ghost"
        size="icon-xs"
        onClick={onRemove}
        className="ml-auto shrink-0 text-muted-foreground hover:text-destructive"
      >
        <X />
      </TooltipIconButton>
    </div>
  );
}

function ConditionGroupsEditor({
  groups,
  groupsOperator,
  label,
  accentClass,
  onGroupsChange,
  onGroupsOperatorChange,
  t,
}: {
  groups: StrategyConditionGroup[];
  groupsOperator: "and" | "or";
  label: string;
  accentClass: string;
  onGroupsChange: (groups: StrategyConditionGroup[]) => void;
  onGroupsOperatorChange: (operator: "and" | "or") => void;
  t: (key: string) => string;
}) {
  const controlStyle = { fontSize: "var(--font-ui)" };
  const conditionCount = groups.reduce(
    (total, group) => total + group.conditions.length,
    0,
  );
  return (
    <section className="overflow-hidden rounded-md border border-border bg-muted/10">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span className={`size-1.5 rounded-full ${accentClass}`} />
          <h3 className="text-caption font-semibold text-foreground">{label}</h3>
          <Badge variant="outline" className="text-micro font-normal text-muted-foreground">
            {conditionCount}
          </Badge>
        </div>
        {groups.length > 1 ? (
          <div className="flex items-center gap-2">
            <span className="text-micro text-muted-foreground">
              {t("backtest.betweenGroups")}
            </span>
            <Select
              value={groupsOperator}
              onValueChange={(value) =>
                onGroupsOperatorChange(value as "and" | "or")
              }
            >
              <SelectTrigger size="sm" className="w-[112px]" style={controlStyle}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="and">{t("backtest.logic.and")}</SelectItem>
                <SelectItem value="or">{t("backtest.logic.or")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}
      </header>
      <div className="grid gap-2 p-3">
        {groups.map((group, groupIndex) => (
          <div
            key={groupIndex}
            className="grid gap-2 rounded-md border border-border bg-card/60 p-2"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-micro text-muted-foreground">
                  {t("backtest.conditionGroup")} {groupIndex + 1}
                </span>
                <Select
                  value={group.operator}
                  onValueChange={(value) =>
                    onGroupsChange(
                      groups.map((item, index) =>
                        index === groupIndex
                          ? { ...item, operator: value as "and" | "or" }
                          : item,
                      ),
                    )
                  }
                >
                  <SelectTrigger size="sm" className="w-[112px]" style={controlStyle}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="and">{t("backtest.logic.and")}</SelectItem>
                    <SelectItem value="or">{t("backtest.logic.or")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant="ghost"
                size="icon-xs"
                style={controlStyle}
                aria-label={t("backtest.deleteGroup")}
                onClick={() =>
                  onGroupsChange(groups.filter((_, index) => index !== groupIndex))
                }
              >
                <Trash2 />
              </Button>
            </div>
            {group.conditions.map((condition, conditionIndex) => (
              <ConditionRow
                key={conditionIndex}
                condition={condition}
                onChange={(next) =>
                  onGroupsChange(
                    groups.map((item, index) =>
                      index === groupIndex
                        ? {
                            ...item,
                            conditions: item.conditions.map((existing, itemIndex) =>
                              itemIndex === conditionIndex ? next : existing,
                            ),
                          }
                        : item,
                    ),
                  )
                }
                onRemove={() =>
                  onGroupsChange(
                    groups.map((item, index) =>
                      index === groupIndex
                        ? {
                            ...item,
                            conditions: item.conditions.filter(
                              (_, itemIndex) => itemIndex !== conditionIndex,
                            ),
                          }
                        : item,
                    ),
                  )
                }
                t={t}
              />
            ))}
            <Button
              variant="ghost"
              size="sm"
              style={controlStyle}
              className="justify-start border border-dashed border-border text-muted-foreground"
              onClick={() =>
                onGroupsChange(
                  groups.map((item, index) =>
                    index === groupIndex
                      ? {
                          ...item,
                          conditions: [...item.conditions, makeDefaultCondition()],
                        }
                      : item,
                  ),
                )
              }
            >
              <Plus />
              {t("backtest.addCondition")}
            </Button>
          </div>
        ))}
        <Button
          variant="ghost"
          size="sm"
          style={controlStyle}
          className="w-full justify-start border border-dashed border-border text-muted-foreground"
          onClick={() =>
            onGroupsChange([
              ...groups,
              { operator: "and", conditions: [makeDefaultCondition()] },
            ])
          }
        >
          <Plus />
          {t("backtest.addGroup")}
        </Button>
      </div>
    </section>
  );
}

// ── BacktestPage ─────────────────────────────────────────

export default function BacktestPage() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Strategy list
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [, setLoading] = useState(true);

  // Editor state
  const [name, setName] = useState("Strategy 1");
  const [config, setConfig] = useState<StrategyConfig>({ ...DEFAULT_CONFIG });
  const [marketOpen, setMarketOpen] = useState(false);
  const [marketQuery, setMarketQuery] = useState("");
  const [marketMatches, setMarketMatches] = useState<MarketInstrumentMatch[]>([]);

  // Delete confirmation
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [runToDelete, setRunToDelete] = useState<BacktestRun | null>(null);

  const [activeTab, setActiveTab] = useState<"backtest" | "history">(
    searchParams.get("tab") === "history" ? "history" : "backtest",
  );
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [historyPage, setHistoryPage] = useState(0);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [compareRuns, setCompareRuns] = useState<BacktestRun[]>([]);
  const [busyRunId, setBusyRunId] = useState<string | null>(null);
  const [optimizationGrids, setOptimizationGrids] = useState<
    OptimizationGridDraft[]
  >([
    {
      id: 1,
      parameter: "stop_loss_pct",
      min: 1,
      max: 5,
      step: 1,
    },
  ]);
  const nextOptimizationGridId = useRef(2);
  const [optimizationObjective, setOptimizationObjective] =
    useState("sharpe_ratio");
  const [trainRatio, setTrainRatio] = useState(0.7);
  const [trainBars, setTrainBars] = useState(500);
  const [testBars, setTestBars] = useState(100);
  const [stepBars, setStepBars] = useState(100);

  // Fetch strategies
  const fetchStrategies = useCallback(async () => {
    try {
      const data = await listStrategies();
      setStrategies(data);
    } catch {
      // toast handled by client
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await listBacktestRuns({
        limit: HISTORY_PAGE_SIZE,
        offset: historyPage * HISTORY_PAGE_SIZE,
      });
      if (data.items.length === 0 && data.total > 0 && historyPage > 0) {
        setHistoryPage((page) => Math.max(0, page - 1));
        return;
      }
      setRuns(data.items);
      setHistoryTotal(data.total);
    } catch {
      // toast handled by client
    }
  }, [historyPage]);

  useEffect(() => {
    if (!user) return;
    fetchStrategies();
  }, [fetchStrategies, user]);

  useEffect(() => {
    if (!user) return;
    fetchRuns();
  }, [fetchRuns, user]);

  useEffect(() => {
    const query = marketQuery.trim();
    if (!marketOpen || !query) {
      setMarketMatches([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(() => {
      searchMarketInstruments(query)
        .then((matches) => {
          if (active) setMarketMatches(matches);
        })
        .catch(() => {
          if (active) setMarketMatches([]);
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [marketOpen, marketQuery]);

  // Load strategy into editor
  const loadStrategy = useCallback(
    (s: Strategy) => {
      setSelectedId(s.id);
      setName(s.name);
      setConfig({
        ...DEFAULT_CONFIG,
        ...s.config,
        direction:
          (s.config.direction as string) === "both"
            ? "long"
            : s.config.direction,
      });
    },
    []
  );

  // Handle new strategy
  const handleNew = useCallback(() => {
    setSelectedId(null);
    setName("Strategy " + (strategies.length + 1));
    setConfig({ ...DEFAULT_CONFIG });
  }, [strategies.length]);

  const persistStrategy = useCallback(async (): Promise<string> => {
    if (selectedId) {
      const updated = await updateStrategy(selectedId, { name, config });
      setConfig(updated.config);
      setStrategies((previous) =>
        previous.map((strategy) =>
          strategy.id === updated.id ? updated : strategy,
        ),
      );
      return updated.id;
    }
    const created = await createStrategy({ name, config });
    setConfig(created.config);
    setStrategies((previous) => [...previous, created]);
    setSelectedId(created.id);
    return created.id;
  }, [config, name, selectedId]);

  // Save strategy
  const handleSave = useCallback(async () => {
    try {
      await persistStrategy();
      showToast(t("backtest.saved"), "success");
    } catch {
      // error toast handled by client
    }
  }, [persistStrategy, showToast, t]);

  // Delete strategy
  const handleDelete = useCallback(async () => {
    if (!selectedId) return;
    try {
      await deleteStrategyApi(selectedId);
      setStrategies((prev) => prev.filter((s) => s.id !== selectedId));
      setSelectedId(null);
      setName("Strategy 1");
      setConfig({ ...DEFAULT_CONFIG });
    } catch {
      // toast handled by client
    }
  }, [selectedId]);

  // Run backtest
  const handleRunBacktest = useCallback(async () => {
    let strategyId: string;
    try {
      strategyId = await persistStrategy();
    } catch {
      return;
    }

    setBacktestRunning(true);

    try {
      const run = await createBacktestRun({
        strategy_id: strategyId,
        date_from: dateFrom || null,
        date_to: dateTo || null,
      });
      fetchRuns();
      navigate(`/backtest/runs/${run.run_id}`);
    } catch {
      setBacktestRunning(false);
    }
  }, [
    dateFrom,
    dateTo,
    fetchRuns,
    navigate,
    persistStrategy,
  ]);

  const handleRunAnalysis = useCallback(
    async (kind: "optimization" | "validation" | "walk_forward") => {
      let strategyId: string;
      try {
        strategyId = await persistStrategy();
      } catch {
        return;
      }
      const grids = optimizationGrids.map((grid) => ({
        parameter: grid.parameter,
        values: parameterValues(grid.min, grid.max, grid.step),
      }));
      if (kind !== "validation") {
        const uniqueParameters = new Set(
          grids.map((grid) => grid.parameter),
        ).size;
        const combinationCount = grids.reduce(
          (count, grid) => count * grid.values.length,
          1,
        );
        if (
          grids.length === 0 ||
          grids.some((grid) => grid.values.length === 0) ||
          uniqueParameters !== grids.length ||
          combinationCount > 200
        ) {
          showToast(t("backtest.invalidOptimizationGrid"));
          return;
        }
      }

      setBacktestRunning(true);
      try {
        const common = {
          strategy_id: strategyId,
          date_from: dateFrom || null,
          date_to: dateTo || null,
        };
        const run =
          kind === "optimization"
            ? await createOptimizationRun({
                ...common,
                objective: optimizationObjective,
                grids,
              })
            : kind === "validation"
              ? await createValidationRun({
                  ...common,
                  train_ratio: trainRatio,
                })
              : await createWalkForwardRun({
                  ...common,
                  objective: optimizationObjective,
                  grids,
                  train_bars: trainBars,
                  test_bars: testBars,
                  step_bars: stepBars,
                });
        fetchRuns();
        navigate(`/backtest/runs/${run.run_id}`);
      } catch {
        setBacktestRunning(false);
      }
    },
    [
      dateFrom,
      dateTo,
      fetchRuns,
      navigate,
      optimizationGrids,
      optimizationObjective,
      persistStrategy,
      showToast,
      stepBars,
      t,
      testBars,
      trainBars,
      trainRatio,
    ],
  );

  const handleOpenRun = useCallback(
    (run: BacktestRun) => {
      navigate(`/backtest/runs/${run.id}?from=history`);
    },
    [navigate],
  );

  const handleCompareRun = useCallback(async (run: BacktestRun) => {
    setBusyRunId(run.id);
    try {
      const detail = await getBacktestRun(run.id);
      setCompareRuns((current) => {
        if (current.some((item) => item.id === detail.id)) {
          return current.filter((item) => item.id !== detail.id);
        }
        return [...current.slice(-1), detail];
      });
    } finally {
      setBusyRunId(null);
    }
  }, []);

  const handleRerun = useCallback(
    async (run: BacktestRun) => {
      setBusyRunId(run.id);
      setBacktestRunning(true);
      try {
        const created = await rerunBacktest(run.id);
        fetchRuns();
        navigate(`/backtest/runs/${created.run_id}?from=history`);
      } catch {
        setBusyRunId(null);
        setBacktestRunning(false);
      }
    },
    [fetchRuns, navigate],
  );

  const handleDeleteRun = useCallback(async () => {
    if (!runToDelete) return;
    setBusyRunId(runToDelete.id);
    try {
      await deleteBacktestRun(runToDelete.id);
      setCompareRuns((current) =>
        current.filter((item) => item.id !== runToDelete.id),
      );
      await fetchRuns();
    } finally {
      setBusyRunId(null);
      setRunToDelete(null);
    }
  }, [fetchRuns, runToDelete]);

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  const btnStyle = {
    fontSize: backtestControlSizes.fontSize,
    fontWeight: backtestControlSizes.fontWeight,
  };
  const inputStyle = { fontSize: backtestControlSizes.fontSize } as const;

  return (
    <>
    <Tabs
      value={activeTab}
      onValueChange={(value) => {
        const tab = value as "backtest" | "history";
        setActiveTab(tab);
        setSearchParams(tab === "history" ? { tab: "history" } : {}, {
          replace: true,
        });
        if (tab === "history") fetchRuns();
      }}
      className="gap-0"
    >
    <FlushPage
      contentClassName="pt-3"
      toolbarAside={
        activeTab === "backtest" ? (
          <div className="flex items-center gap-2">
            <TooltipIconButton
              label={t("backtest.save")}
              variant="outline"
              size={backtestControlSizes.iconAction}
              style={btnStyle}
              onClick={handleSave}
            >
              <Save />
            </TooltipIconButton>
            {selectedId && (
              <TooltipIconButton
                label={t("backtest.delete")}
                variant="outline"
                size={backtestControlSizes.iconAction}
                onClick={() => setDeleteConfirmOpen(true)}
              >
                <Trash2 />
              </TooltipIconButton>
            )}
            <TooltipIconButton
              label={t("backtest.runBacktest")}
              size={backtestControlSizes.iconAction}
              style={btnStyle}
              onClick={handleRunBacktest}
              disabled={backtestRunning}
            >
              {backtestRunning ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Play />
              )}
            </TooltipIconButton>
          </div>
        ) : null
      }
      toolbar={
        <div className="flex items-center gap-3">
          <TabsList variant="line" className="h-7 gap-3 p-0">
            <TabsTrigger
              value="backtest"
              style={btnStyle}
              className={animatedLineTabClassName}
            >
              {t("backtest.tab.backtest")}
            </TabsTrigger>
            <TabsTrigger
              value="history"
              style={btnStyle}
              className={animatedLineTabClassName}
            >
              {t("backtest.tab.history")}
            </TabsTrigger>
          </TabsList>
          {activeTab === "backtest" ? (
            <>
              <span
                className="h-4 w-px shrink-0 bg-border"
                aria-hidden="true"
              />
              <Select
                value={selectedId ?? "__new__"}
                onValueChange={(val) => {
                  if (val === "__new__") {
                    handleNew();
                  } else {
                    const s = strategies.find((s) => s.id === val);
                    if (s) loadStrategy(s);
                  }
                }}
              >
                <SelectTrigger
                  size="sm"
                  className="w-[200px]"
                  style={inputStyle}
                >
                  <SelectValue placeholder={t("backtest.newStrategy")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="__new__">
                      <Plus className="mr-1 inline-block size-3.5" />
                      {t("backtest.newStrategy")}
                    </SelectItem>
                    {strategies.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </>
          ) : null}
        </div>
      }
    >
      <TabsContent value="backtest" className="mt-0 flex flex-col gap-4">
        {/* ── Strategy Editor ── */}
        <div className="grid items-start gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex min-w-0 flex-col gap-3">
            <Card className="gap-0 overflow-hidden py-0">
              <CardHeader className="border-b border-border bg-muted/15 px-4 py-2.5">
                <CardTitle className="text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t("backtest.section.market")}
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(220px,1.5fr)_minmax(140px,0.8fr)_100px_auto]">
                <div className="grid min-w-0 gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.strategyName")}
                  </label>
                  <Input
                    className="h-8 w-full"
                    style={inputStyle}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t("backtest.strategyName")}
                  />
                </div>

                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.symbol")}
                  </label>
                  <Popover
                    open={marketOpen}
                    onOpenChange={(open) => {
                      setMarketOpen(open);
                      if (!open) setMarketQuery("");
                    }}
                  >
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 w-full justify-between font-medium"
                        style={btnStyle}
                      >
                        <span className="truncate">
                          {config.symbol}
                          {config.series_id ? (
                            <span className="ml-1 text-caption font-normal text-muted-foreground">
                              · {config.series_id.split(":").slice(-1)[0]}
                            </span>
                          ) : null}
                        </span>
                        <ChevronDown className="size-[var(--icon-xs)] opacity-50" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent
                      className="w-[320px] p-0"
                      align="start"
                    >
                      <Command
                        shouldFilter={false}
                        className="[&_[data-slot=command-input-wrapper]]:h-8 [&_[data-slot=command-input-wrapper]]:px-2.5 [&_[data-slot=command-input-wrapper]_svg]:size-[var(--icon-xs)]"
                      >
                        <CommandInput
                          className="h-8 py-1.5"
                          style={{ fontSize: "var(--font-caption)" }}
                          value={marketQuery}
                          onValueChange={setMarketQuery}
                          placeholder={t("symbol.searchPlaceholder")}
                        />
                        <CommandList>
                          <CommandEmpty>
                            {t("symbol.noMatches")}
                          </CommandEmpty>
                          <CommandGroup
                            heading={
                              marketQuery.trim()
                                ? undefined
                                : t("symbol.popular")
                            }
                          >
                            {(marketQuery.trim()
                              ? marketMatches
                              : PRESET_MARKET_MATCHES
                            ).map((match) => (
                              <CommandItem
                                key={match.series_id}
                                value={match.series_id}
                                onSelect={() => {
                                  setConfig((current) => ({
                                    ...current,
                                    symbol: match.symbol,
                                    series_id: match.series_id,
                                  }));
                                  setMarketQuery("");
                                  setMarketOpen(false);
                                }}
                              >
                                <span className="min-w-0 flex-1">
                                  <span className="block truncate text-ui font-medium">
                                    {match.symbol}
                                  </span>
                                  <span className="block truncate text-caption text-muted-foreground">
                                    {match.name}
                                  </span>
                                </span>
                                <span className="text-caption text-muted-foreground">
                                  {match.venue ?? match.series_kind}
                                </span>
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        </CommandList>
                      </Command>
                    </PopoverContent>
                  </Popover>
                </div>

                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.interval")}
                  </label>
                  <Select
                    value={config.interval}
                    onValueChange={(val) =>
                      setConfig((c) => ({ ...c, interval: val }))
                    }
                  >
                    <SelectTrigger size="sm" className="w-full" style={inputStyle}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {INTERVAL_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.direction")}
                  </label>
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    size={backtestControlSizes.toggle}
                    value={config.direction}
                    onValueChange={(val) => {
                      if (val)
                        setConfig((c) => ({
                          ...c,
                          direction: val as StrategyConfig["direction"],
                        }));
                    }}
                    spacing={0}
                  >
                    <ToggleGroupItem value="long" style={btnStyle}>
                      {t("backtest.directionLong")}
                    </ToggleGroupItem>
                    <ToggleGroupItem value="short" style={btnStyle}>
                      {t("backtest.directionShort")}
                    </ToggleGroupItem>
                  </ToggleGroup>
                </div>
              </CardContent>
            </Card>

            <Card className="gap-0 overflow-hidden py-0">
              <CardHeader className="border-b border-border bg-muted/15 px-4 py-2.5">
                <CardTitle className="text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t("backtest.section.logic")}
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 px-4 py-3">
                <ConditionGroupsEditor
                  groups={config.entry_groups}
                  groupsOperator={config.entry_groups_operator}
                  label={t("backtest.entryConditions")}
                  accentClass="bg-primary"
                  onGroupsChange={(entryGroups) =>
                    setConfig((current) => ({
                      ...current,
                      entry_groups: entryGroups,
                    }))
                  }
                  onGroupsOperatorChange={(entryGroupsOperator) =>
                    setConfig((current) => ({
                      ...current,
                      entry_groups_operator: entryGroupsOperator,
                    }))
                  }
                  t={t}
                />

                <ConditionGroupsEditor
                  groups={config.exit_groups}
                  groupsOperator={config.exit_groups_operator}
                  label={t("backtest.exitConditions")}
                  accentClass="bg-[var(--market-warning)]"
                  onGroupsChange={(exitGroups) =>
                    setConfig((current) => ({
                      ...current,
                      exit_groups: exitGroups,
                    }))
                  }
                  onGroupsOperatorChange={(exitGroupsOperator) =>
                    setConfig((current) => ({
                      ...current,
                      exit_groups_operator: exitGroupsOperator,
                    }))
                  }
                  t={t}
                />
              </CardContent>
            </Card>
          </div>

          <Card className="gap-0 overflow-hidden py-0 xl:sticky xl:top-[calc(var(--page-topbar-height)+3.25rem)]">
            <CardHeader className="border-b border-border bg-muted/15 px-4 py-2.5">
              <CardTitle className="text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                {t("backtest.section.risk")}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 px-4 py-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.stopLossLabel")}
                  </label>
                  <div className="relative">
                    <Input
                      type="number"
                      className="h-8 w-full pr-8"
                      style={inputStyle}
                      value={config.stop_loss_pct ?? ""}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          stop_loss_pct: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }))
                      }
                      placeholder={t("backtest.optional")}
                    />
                    <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-micro text-muted-foreground">%</span>
                  </div>
                </div>

                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.takeProfitLabel")}
                  </label>
                  <div className="relative">
                    <Input
                      type="number"
                      className="h-8 w-full pr-8"
                      style={inputStyle}
                      value={config.take_profit_pct ?? ""}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          take_profit_pct: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }))
                      }
                      placeholder={t("backtest.optional")}
                    />
                    <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-micro text-muted-foreground">%</span>
                  </div>
                </div>
              </div>

              <div className="grid gap-3">
                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.trailingStop")}
                  </label>
                  <Input
                    type="number"
                    min="0"
                    step="0.1"
                    className="h-8 w-full"
                    style={inputStyle}
                    value={config.trailing_stop_pct ?? ""}
                    placeholder={t("backtest.optional")}
                    onChange={(event) =>
                      setConfig((current) => ({
                        ...current,
                        trailing_stop_pct: event.target.value
                          ? Number(event.target.value)
                          : null,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.breakevenTrigger")}
                  </label>
                  <Input
                    type="number"
                    min="0"
                    step="0.1"
                    className="h-8 w-full"
                    style={inputStyle}
                    value={config.breakeven_trigger_pct ?? ""}
                    placeholder={t("backtest.optional")}
                    onChange={(event) =>
                      setConfig((current) => ({
                        ...current,
                        breakeven_trigger_pct: event.target.value
                          ? Number(event.target.value)
                          : null,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-1">
                  <label className="text-caption text-muted-foreground">
                    {t("backtest.maxHoldingBars")}
                  </label>
                  <Input
                    type="number"
                    min="1"
                    step="1"
                    className="h-8 w-full"
                    style={inputStyle}
                    value={config.max_holding_bars ?? ""}
                    placeholder={t("backtest.optional")}
                    onChange={(event) =>
                      setConfig((current) => ({
                        ...current,
                        max_holding_bars: event.target.value
                          ? Number(event.target.value)
                          : null,
                      }))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-1">
                <label className="text-caption text-muted-foreground">
                  {t("backtest.positionSize")}
                </label>
                <Input
                  type="number"
                  min="0.0001"
                  step="1"
                  className="h-8 w-full"
                  style={inputStyle}
                  value={config.position_size}
                  onChange={(e) =>
                    setConfig((c) => ({
                      ...c,
                      position_size: Number(e.target.value),
                    }))
                  }
                />
              </div>

              <div className="border-t border-border pt-4">
                <div className="mb-3 text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t("backtest.section.execution")}
                </div>

                <div className="grid gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-1">
                      <label className="text-caption text-muted-foreground">
                        {t("backtest.dateFrom")}
                      </label>
                      <Input
                        type="date"
                        className="h-8 w-full"
                        style={inputStyle}
                        value={dateFrom}
                        max={dateTo || undefined}
                        onChange={(event) => setDateFrom(event.target.value)}
                      />
                    </div>
                    <div className="grid gap-1">
                      <label className="text-caption text-muted-foreground">
                        {t("backtest.dateTo")}
                      </label>
                      <Input
                        type="date"
                        className="h-8 w-full"
                        style={inputStyle}
                        value={dateTo}
                        min={dateFrom || undefined}
                        onChange={(event) => setDateTo(event.target.value)}
                      />
                    </div>
                  </div>

                  <div className="grid gap-1">
                    <label className="text-caption text-muted-foreground">
                      {t("backtest.lookback")}
                    </label>
                    <ToggleGroup
                      type="single"
                      variant="outline"
                      size={backtestControlSizes.toggle}
                      value={String(config.lookback_months)}
                      onValueChange={(val) => {
                        if (val)
                          setConfig((c) => ({
                            ...c,
                            lookback_months: Number(val),
                          }));
                      }}
                      spacing={0}
                      className="grid grid-cols-4"
                    >
                      {LOOKBACK_OPTIONS.map((m) => (
                        <ToggleGroupItem
                          key={m}
                          value={String(m)}
                          style={btnStyle}
                          aria-label={t("backtest.months", { count: m })}
                        >
                          {m}M
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </div>

                  <div className="grid gap-1">
                    <label className="text-caption text-muted-foreground">
                      {t("backtest.initialCash")}
                    </label>
                    <Input
                      type="number"
                      min="1"
                      className="h-8 w-full"
                      style={inputStyle}
                      value={config.initial_cash}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          initial_cash: Number(e.target.value),
                        }))
                      }
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-1">
                      <label className="text-caption text-muted-foreground">
                        {t("backtest.commission")}
                      </label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0"
                          step="0.1"
                          className="h-8 w-full pr-10"
                          style={inputStyle}
                          value={config.commission_bps}
                          onChange={(e) =>
                            setConfig((c) => ({
                              ...c,
                              commission_bps: Number(e.target.value),
                            }))
                          }
                        />
                        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-micro text-muted-foreground">bps</span>
                      </div>
                    </div>

                    <div className="grid gap-1">
                      <label className="text-caption text-muted-foreground">
                        {t("backtest.spread")}
                      </label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0"
                          step="0.1"
                          className="h-8 w-full pr-10"
                          style={inputStyle}
                          value={config.spread_bps}
                          onChange={(e) =>
                            setConfig((c) => ({
                              ...c,
                              spread_bps: Number(e.target.value),
                            }))
                          }
                        />
                        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-micro text-muted-foreground">bps</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-t border-border pt-4">
                <div className="mb-3 text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t("backtest.section.validation")}
                </div>
                <div className="grid gap-3">
                  <div className="grid gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <label className="text-caption text-muted-foreground">
                        {t("backtest.optimizationParameters")}
                      </label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2"
                        style={btnStyle}
                        disabled={
                          nextOptimizationParameter(optimizationGrids) == null
                        }
                        onClick={() => {
                          const parameter =
                            nextOptimizationParameter(optimizationGrids);
                          if (!parameter) return;
                          setOptimizationGrids((current) => [
                            ...current,
                            {
                              id: nextOptimizationGridId.current++,
                              parameter,
                              min: 1,
                              max: 5,
                              step: 1,
                            },
                          ]);
                        }}
                      >
                        <Plus className="size-[var(--icon-xs)]" />
                        {t("backtest.addParameter")}
                      </Button>
                    </div>
                    <div className="grid grid-cols-[minmax(0,1fr)_64px_64px_64px_28px] gap-1 text-micro text-muted-foreground">
                      <span>{t("backtest.optimizationParameter")}</span>
                      <span>{t("backtest.minimum")}</span>
                      <span>{t("backtest.maximum")}</span>
                      <span>{t("backtest.step")}</span>
                      <span />
                    </div>
                    <div className="grid gap-2">
                      {optimizationGrids.map((grid) => (
                        <div
                          key={grid.id}
                          className="grid grid-cols-[minmax(0,1fr)_64px_64px_64px_28px] items-center gap-1"
                        >
                          <Select
                            value={grid.parameter}
                            onValueChange={(parameter) =>
                              setOptimizationGrids((current) =>
                                current.map((item) =>
                                  item.id === grid.id
                                    ? {
                                        ...item,
                                        parameter:
                                          parameter as OptimizationParameter,
                                      }
                                    : item,
                                ),
                              )
                            }
                          >
                            <SelectTrigger
                              size="sm"
                              className="w-full"
                              style={inputStyle}
                            >
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {OPTIMIZATION_PARAMETERS.map((parameter) => (
                                <SelectItem
                                  key={parameter}
                                  value={parameter}
                                  disabled={optimizationGrids.some(
                                    (item) =>
                                      item.id !== grid.id &&
                                      item.parameter === parameter,
                                  )}
                                >
                                  {t(`backtest.parameter.${parameter}`)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Input
                            type="number"
                            style={inputStyle}
                            value={grid.min}
                            aria-label={t("backtest.minimum")}
                            onChange={(event) =>
                              setOptimizationGrids((current) =>
                                current.map((item) =>
                                  item.id === grid.id
                                    ? {
                                        ...item,
                                        min: Number(event.target.value),
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                          <Input
                            type="number"
                            style={inputStyle}
                            value={grid.max}
                            aria-label={t("backtest.maximum")}
                            onChange={(event) =>
                              setOptimizationGrids((current) =>
                                current.map((item) =>
                                  item.id === grid.id
                                    ? {
                                        ...item,
                                        max: Number(event.target.value),
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                          <Input
                            type="number"
                            style={inputStyle}
                            value={grid.step}
                            aria-label={t("backtest.step")}
                            onChange={(event) =>
                              setOptimizationGrids((current) =>
                                current.map((item) =>
                                  item.id === grid.id
                                    ? {
                                        ...item,
                                        step: Number(event.target.value),
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                          <TooltipIconButton
                            label={t("common.delete")}
                            size="icon-xs"
                            disabled={optimizationGrids.length === 1}
                            onClick={() =>
                              setOptimizationGrids((current) =>
                                current.filter((item) => item.id !== grid.id),
                              )
                            }
                          >
                            <X />
                          </TooltipIconButton>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-1">
                    <label className="text-caption text-muted-foreground">
                      {t("backtest.objective")}
                    </label>
                    <Select
                      value={optimizationObjective}
                      onValueChange={setOptimizationObjective}
                    >
                      <SelectTrigger size="sm" className="w-full" style={inputStyle}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[
                          "sharpe_ratio",
                          "total_return_pct",
                          "profit_factor",
                          "max_drawdown_pct",
                        ].map((objective) => (
                          <SelectItem key={objective} value={objective}>
                            {t(`backtest.objective.${objective}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <Input
                      type="number"
                      min="0.5"
                      max="0.9"
                      step="0.05"
                      style={inputStyle}
                      value={trainRatio}
                      aria-label={t("backtest.trainRatio")}
                      onChange={(event) => setTrainRatio(Number(event.target.value))}
                    />
                    <Input
                      type="number"
                      min="3"
                      step="1"
                      style={inputStyle}
                      value={trainBars}
                      aria-label={t("backtest.trainBars")}
                      onChange={(event) => setTrainBars(Number(event.target.value))}
                    />
                    <Input
                      type="number"
                      min="3"
                      step="1"
                      style={inputStyle}
                      value={testBars}
                      aria-label={t("backtest.testBars")}
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        setTestBars(value);
                        setStepBars(value);
                      }}
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      style={btnStyle}
                      disabled={backtestRunning}
                      onClick={() => handleRunAnalysis("optimization")}
                    >
                      {t("backtest.optimize")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      style={btnStyle}
                      disabled={backtestRunning}
                      onClick={() => handleRunAnalysis("validation")}
                    >
                      {t("backtest.validate")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      style={btnStyle}
                      disabled={backtestRunning}
                      onClick={() => handleRunAnalysis("walk_forward")}
                    >
                      {t("backtest.walkForward")}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </TabsContent>
      <TabsContent value="history" className="mt-0">
        <BacktestHistoryPanel
          runs={runs}
          page={historyPage}
          pageSize={HISTORY_PAGE_SIZE}
          total={historyTotal}
          compareRuns={compareRuns}
          busyRunId={busyRunId}
          buttonStyle={btnStyle}
          t={t}
          onOpen={handleOpenRun}
          onRerun={handleRerun}
          onCompare={handleCompareRun}
          onDelete={setRunToDelete}
          onPageChange={setHistoryPage}
        />
      </TabsContent>
    </FlushPage>
    </Tabs>
      <ConfirmDialog
        open={deleteConfirmOpen}
        onOpenChange={setDeleteConfirmOpen}
        title={t("backtest.confirmDelete")}
        onConfirm={() => {
          setDeleteConfirmOpen(false);
          handleDelete();
        }}
      />
      <ConfirmDialog
        open={runToDelete !== null}
        onOpenChange={(open) => {
          if (!open) setRunToDelete(null);
        }}
        title={t("backtest.deleteRun")}
        description={t("backtest.deleteRunHint")}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={handleDeleteRun}
        destructive
      />
    </>
  );
}
