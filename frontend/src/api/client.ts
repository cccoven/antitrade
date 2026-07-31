import axios from "axios";
import i18n from "../i18n";
import { showToast } from "../components/Toast";
import type { User } from "../auth/auth-types";
import { API_BASE_URL, apiUrl } from "./base-url";

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

class BillingRequiredError extends Error {}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  config.headers["Accept-Language"] = i18n.language;
  const token = window.localStorage.getItem("antitrade.auth.token");
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      window.localStorage.removeItem("antitrade.auth.token");
      window.dispatchEvent(new Event("auth:unauthorized"));
    }
    if (axios.isAxiosError<ApiResponse<unknown>>(error) && error.response?.status === 402) {
      window.dispatchEvent(new CustomEvent("billing:upgrade-required", {
        detail: error.response.data?.data ?? {},
      }));
    }
    return Promise.reject(error);
  }
);

/**
 * Append the auth token as a query parameter so `<img src=...>` tags can
 * authenticate against same-origin protected uploads endpoints. Headers
 * aren't an option for native image loading, so fall back to ?token=.
 */
export function authedAssetUrl(url: string | null | undefined): string {
  if (!url) return url ?? "";
  const token = window.localStorage.getItem("antitrade.auth.token");
  const normalizedUrl = apiUrl(url);
  if (!token) return normalizedUrl;
  const sep = normalizedUrl.includes("?") ? "&" : "?";
  return `${normalizedUrl}${sep}token=${encodeURIComponent(token)}`;
}

function getGenericErrorMessage() {
  return i18n.t("error.generic");
}

function getNetworkErrorMessage() {
  return i18n.t("error.network");
}

function toUserError(error: unknown): Error {
  if (axios.isAxiosError<ApiResponse<unknown>>(error)) {
    if (!error.response) {
      return new Error(getNetworkErrorMessage());
    }

    const message = error.response.data?.message;
    if (error.response.status === 402) {
      return new BillingRequiredError(
        typeof message === "string" && message.trim() ? message : getGenericErrorMessage(),
      );
    }
    if (typeof message === "string" && message.trim()) {
      return new Error(message);
    }

    return new Error(getGenericErrorMessage());
  }

  return new Error(getGenericErrorMessage());
}

export async function unwrapResponse<T>(promise: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  try {
    const { data } = await promise;
    if (data.code !== 0) {
      throw new Error(data.message || getGenericErrorMessage());
    }
    return data.data;
  } catch (error) {
    const userError = toUserError(error);
    if (!(userError instanceof BillingRequiredError)) showToast(userError.message);
    throw userError;
  }
}

/**
 * Like unwrapResponse but never surfaces a toast — for background polling
 * where a transient failure should stay silent instead of nagging the user.
 */
async function unwrapResponseSilent<T>(promise: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const { data } = await promise;
  if (data.code !== 0) {
    throw new Error(data.message || getGenericErrorMessage());
  }
  return data.data;
}

export interface AnalyzeRequest {
  symbol: string;
  exchange: string;
  interval: string;
  lang?: string;
  force_refresh?: boolean;
}

export interface AnalyzeResult {
  symbol: string;
  exchange: string;
  interval: string;
  analysis: string;
  analyzed_at: string;
}

export interface AnalyzeJobResponse {
  job_id: string;
  symbol: string;
  exchange: string;
  interval: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  result: AnalyzeResult | null;
  error: string | null;
}

export async function createAnalyzeJob(req: AnalyzeRequest): Promise<AnalyzeJobResponse> {
  return unwrapResponse(
    api.post<ApiResponse<AnalyzeJobResponse>>("/analyze/jobs", req)
  );
}

export async function getAnalyzeJob(jobId: string): Promise<AnalyzeJobResponse> {
  return unwrapResponse(api.get<ApiResponse<AnalyzeJobResponse | null>>(`/analyze/jobs/${jobId}`))
    .then((data) => {
      if (!data) {
        throw new Error(getGenericErrorMessage());
      }
      return data;
    });
}

export async function fetchLatestAnalysis(
  symbol: string,
  exchange: string,
  interval: string
): Promise<AnalyzeResult | null> {
  return unwrapResponse(
    api.get<ApiResponse<AnalyzeResult | null>>("/analyze/latest", {
      params: { symbol, exchange, interval },
    })
  );
}

// ─── Trading Tools ──────────────────────────────────────────

export type TradingToolAssetClass = "stock" | "forex" | "crypto" | "futures";

export interface PositionSizeRequest {
  asset_class: TradingToolAssetClass;
  symbol: string;
  direction: "long" | "short";
  entry_price: number;
  stop_loss: number;
  target_price?: number | null;
  account_size: number;
  risk_percent: number;
  point_value?: number | null;
}

export interface PositionSizeResult {
  asset_class: TradingToolAssetClass;
  symbol: string;
  direction: "long" | "short";
  price_risk: number;
  point_value: number | null;
  unit_risk: number | null;
  risk_budget: number | null;
  quantity: number | null;
  max_quantity: number | null;
  risk_amount: number | null;
  risk_percent: number | null;
  reward_risk: number | null;
  potential_reward: number | null;
  instrument: Record<string, unknown> | null;
  warnings: string[];
}

export interface ExpectancyRequest {
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  cost_per_trade: number;
  target_profit?: number | null;
}

export interface ExpectancyResult {
  gross_expectancy: number;
  expectancy: number;
  break_even_win_rate: number | null;
  gross_profit_factor: number | null;
  cost_drag: number;
  trades_to_target: number | null;
}

export interface DrawdownRequest {
  starting_equity: number;
  current_equity: number;
  max_drawdown_percent: number;
  risk_per_trade_percent: number;
}

export interface DrawdownResult {
  drawdown_amount: number;
  drawdown_percent: number;
  recovery_gain_percent: number;
  floor_equity: number;
  remaining_loss_budget: number;
  remaining_budget_percent: number;
  losses_until_limit: number | null;
  limit_breached: boolean;
}

export interface MonteCarloRequest {
  starting_equity: number;
  target_return_percent: number;
  max_drawdown_percent: number;
  win_rate: number;
  avg_win_r: number;
  avg_loss_r: number;
  risk_per_trade_percent: number;
  trades: number;
  simulations: number;
  seed?: number;
}

export interface MonteCarloResult {
  target_equity: number;
  ruin_floor: number;
  target_probability: number;
  risk_of_ruin: number;
  median_ending_equity: number;
  p10_ending_equity: number;
  p90_ending_equity: number;
  median_max_drawdown: number;
  p90_max_drawdown: number;
  percentile_bands: { trade: number; p10: number; p50: number; p90: number }[];
  simulations: number;
  seed: number;
}

export interface CostImpactRequest {
  trades_count: number;
  gross_pnl: number;
  commission_per_trade: number;
  slippage_per_trade: number;
  spread_per_trade: number;
}

export interface CostImpactResult {
  cost_per_trade: number;
  total_cost: number;
  net_pnl: number;
  gross_average: number;
  net_average: number;
  cost_drag_percent: number | null;
  break_even_gross_per_trade: number;
}

export async function calculatePositionSize(req: PositionSizeRequest): Promise<PositionSizeResult> {
  return unwrapResponse(api.post<ApiResponse<PositionSizeResult>>("/trading-tools/position-size", req));
}

export async function calculateExpectancy(req: ExpectancyRequest): Promise<ExpectancyResult> {
  return unwrapResponse(api.post<ApiResponse<ExpectancyResult>>("/trading-tools/expectancy", req));
}

export async function calculateDrawdown(req: DrawdownRequest): Promise<DrawdownResult> {
  return unwrapResponse(api.post<ApiResponse<DrawdownResult>>("/trading-tools/drawdown", req));
}

export async function calculateMonteCarlo(req: MonteCarloRequest): Promise<MonteCarloResult> {
  return unwrapResponse(api.post<ApiResponse<MonteCarloResult>>("/trading-tools/monte-carlo", req));
}

export async function calculateCostImpact(req: CostImpactRequest): Promise<CostImpactResult> {
  return unwrapResponse(api.post<ApiResponse<CostImpactResult>>("/trading-tools/cost-impact", req));
}

// ─── Journal Types ───────────────────────────────────────────

export interface UploadedAsset {
  id: string;
  url: string;
  original_name: string | null;
  mime_type: string;
  width: number | null;
  height: number | null;
  size_bytes: number;
  created_at: string;
}

export interface ImageAnnotation {
  id: string;
  asset_id: string;
  x_ratio: number;
  y_ratio: number;
  body: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface ImageAnnotationInput {
  x_ratio: number;
  y_ratio: number;
  body: string;
}

export interface TradeImage {
  id: string;
  asset_id: string;
  url: string;
  label: string;
  sort_order: number;
  original_name: string | null;
  mime_type: string;
  width: number | null;
  height: number | null;
  created_at: string;
}

export interface Trade {
  id: string;
  symbol: string;
  series_id: string | null;
  direction: "long" | "short";
  position_status: "open" | "closed";
  exchange: string | null;
  open_price: number | null;
  close_price: number | null;
  quantity: number | null;
  open_time: string | null;
  close_time: string | null;
  fees: number;
  pnl: number | null;
  tags: string[];
  notes: string;
  ai_review: string | null;
  source: string;
  strategy_id: string | null;
  plan_id: string | null;
  target_price: number | null;
  stop_loss: number | null;
  setup_type: string | null;
  emotional_state: string | null;
  mistakes: string[];
  confidence: number | null;
  execution_quality: number | null;
  compliance: ComplianceSummary;
  images: TradeImage[];
  created_at: string;
  updated_at: string;
}

export interface CreateTradeRequest {
  symbol: string;
  series_id?: string | null;
  direction: "long" | "short";
  position_status?: "open" | "closed";
  exchange?: string | null;
  open_price?: number | null;
  close_price?: number | null;
  quantity?: number | null;
  open_time?: string | null;
  close_time?: string | null;
  fees?: number;
  pnl?: number | null;
  tags?: string[];
  notes?: string;
  source?: string;
  strategy_id?: string | null;
  plan_id?: string | null;
  target_price?: number | null;
  stop_loss?: number | null;
  setup_type?: string | null;
  emotional_state?: string | null;
  mistakes?: string[];
  confidence?: number | null;
  execution_quality?: number | null;
  image_asset_ids?: string[];
}

export interface UpdateTradeRequest {
  symbol?: string;
  series_id?: string | null;
  direction?: string;
  position_status?: "open" | "closed";
  exchange?: string | null;
  open_price?: number | null;
  close_price?: number | null;
  quantity?: number | null;
  open_time?: string | null;
  close_time?: string | null;
  fees?: number | null;
  pnl?: number | null;
  tags?: string[];
  notes?: string;
  strategy_id?: string | null;
  plan_id?: string | null;
  target_price?: number | null;
  stop_loss?: number | null;
  setup_type?: string | null;
  emotional_state?: string | null;
  mistakes?: string[];
  confidence?: number | null;
  execution_quality?: number | null;
  image_asset_ids?: string[];
}

export type ComplianceStatus = "passed" | "failed" | "not_applicable";

export interface ComplianceResult {
  rule_id: string | null;
  rule_name: string;
  rule_type: TradingRuleType;
  weight: TradingRuleWeight;
  status: ComplianceStatus;
  detail: string;
}

export interface ComplianceSummary {
  score: number | null;
  passed: number;
  failed: number;
  not_applicable: number;
  results: ComplianceResult[];
}

export interface TradePlan {
  id: string;
  symbol: string;
  series_id: string | null;
  market: string;
  direction: "long" | "short";
  entry_price: number;
  target_price: number | null;
  stop_loss: number;
  account_size: number;
  risk_percent: number;
  risk_amount: number;
  quantity: number | null;
  risk_reward: number | null;
  thesis: string;
  strategy_id: string | null;
  status: "active" | "converted";
  created_at: string;
  updated_at: string;
}

export interface CreateTradePlanRequest {
  symbol: string;
  series_id?: string | null;
  market: string;
  direction: "long" | "short";
  entry_price: number;
  target_price?: number | null;
  stop_loss: number;
  account_size: number;
  risk_percent: number;
  thesis?: string;
  strategy_id?: string | null;
}

export type TradingRuleType =
  | "max_risk_percent"
  | "min_risk_reward"
  | "max_trades_per_day"
  | "min_confidence"
  | "require_stop_loss"
  | "require_notes";

export type TradingRuleWeight = "critical" | "important" | "nice_to_have";

export interface TradingRule {
  id: string;
  name: string;
  rule_type: TradingRuleType;
  threshold: number | null;
  weight: TradingRuleWeight;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ComplianceCheckRequest {
  symbol?: string;
  direction: "long" | "short";
  open_price?: number | null;
  entry_price?: number | null;
  target_price?: number | null;
  stop_loss?: number | null;
  quantity?: number | null;
  account_size?: number | null;
  open_time?: string | null;
  notes?: string;
  thesis?: string;
  confidence?: number | null;
  plan_id?: string | null;
}

export interface TradeStats {
  total_trades: number;
  total_pnl: number;
  winners: number;
  losers: number;
  breakeven_trades: number;
  total_contracts: number;
  winning_contracts: number;
  losing_contracts: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  max_drawdown_from: string;
  max_drawdown_to: string;
  max_run_up: number;
  max_run_up_from: string;
  max_run_up_to: string;
  max_consecutive_losses: number;
  avg_holding_seconds: number;
  avg_holding_winners: number;
  avg_holding_losers: number;
  longest_holding_all: number;
  longest_holding_winners: number;
  longest_holding_losers: number;
  avg_win: number;
  avg_loss: number;
  largest_winner: number;
  largest_loser: number;
  std_winner: number;
  std_loser: number;
  total_profit: number;
  total_loss: number;
  gross_total_pnl: number;
  total_fees: number;
  expectancy: number;
  pnl_before_range: number;
  win_loss_ratio: number;
  sharpe_ratio: number;
  by_symbol: GroupStats[];
  by_direction: GroupStats[];
  by_tag: GroupStats[];
  by_hour_weekday: { weekday: number; hour: number; trades: number; wins: number }[];
  equity_curve: { time: string; equity: number }[];
  per_trade_series: { time: string; pnl_net: number; pnl_gross: number }[];
  distribution_series: number[];
  pnl_by_hour: { hour: number; total_pnl: number; count: number }[];
}

export interface GroupStats {
  [key: string]: string | number;
  count: number;
  total_pnl: number;
  win_rate: number;
}

export interface JournalCalendarDaySummary {
  date: string;
  trade_count: number;
  total_pnl: number;
  win_rate: number;
}

export interface JournalCalendarWeekSummary {
  week_index: number;
  label: string;
  trade_count: number;
  active_days: number;
  total_pnl: number;
  win_rate: number;
}

export interface JournalCalendarSummary {
  month: string;
  days: JournalCalendarDaySummary[];
  weeks: JournalCalendarWeekSummary[];
}

export interface RecognitionResult {
  trades: Partial<CreateTradeRequest>[];
  confidence: number;
  raw_text?: string;
}

export interface JournalJobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: string | null;
  error?: string | null;
  created_at?: string;
}

export interface DailyReview {
  id: string;
  user_id: string;
  review_date: string;
  title: string;
  body: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface DailyReviewDraft {
  title: string;
  body: string;
  tags: string[];
}

export interface DailyReviewBundle {
  review: DailyReview;
  stats: TradeStats;
  trades: Trade[];
}

export type DailyReviewAssistAction =
  | "title"
  | "summary"
  | "organize"
  | "expand"
  | "suggest";

export interface DailyReviewAssistResponse {
  action: DailyReviewAssistAction;
  suggestions: string[];
}

// ─── Pagination ──────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ─── Journal API ─────────────────────────────────────────────

export async function uploadAsset(file: File): Promise<UploadedAsset> {
  const body = new FormData();
  body.append("file", file);
  return unwrapResponse(
    api.post<ApiResponse<UploadedAsset>>("/uploads", body, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  );
}

export async function fetchImageAnnotations(
  assetId: string,
): Promise<ImageAnnotation[]> {
  const data = await unwrapResponse(
    api.get<ApiResponse<{ items: ImageAnnotation[] }>>(
      `/uploads/${assetId}/annotations`,
    ),
  );
  return data.items;
}

export async function replaceImageAnnotations(
  assetId: string,
  items: ImageAnnotationInput[],
): Promise<ImageAnnotation[]> {
  const data = await unwrapResponse(
    api.put<ApiResponse<{ items: ImageAnnotation[] }>>(
      `/uploads/${assetId}/annotations`,
      { items },
    ),
  );
  return data.items;
}

export async function createTrade(req: CreateTradeRequest): Promise<Trade> {
  return unwrapResponse(api.post<ApiResponse<Trade>>("/journal/trades", req));
}

export async function listTrades(params?: {
  symbol?: string; direction?: string; position_status?: "open" | "closed"; tag?: string;
  date_from?: string; date_to?: string;
  limit?: number; offset?: number;
}): Promise<PaginatedResponse<Trade>> {
  return unwrapResponse(api.get<ApiResponse<PaginatedResponse<Trade>>>("/journal/trades", { params }));
}

export async function getTrade(id: string): Promise<Trade> {
  return unwrapResponse(api.get<ApiResponse<Trade>>(`/journal/trades/${id}`));
}

export async function updateTrade(id: string, req: UpdateTradeRequest): Promise<Trade> {
  return unwrapResponse(api.put<ApiResponse<Trade>>(`/journal/trades/${id}`, req));
}

export async function deleteTrade(id: string): Promise<null> {
  return unwrapResponse(api.delete<ApiResponse<null>>(`/journal/trades/${id}`));
}

export async function createTradePlan(req: CreateTradePlanRequest): Promise<TradePlan> {
  return unwrapResponse(api.post<ApiResponse<TradePlan>>("/journal/plans", req));
}

export async function listTradePlans(
  status: "active" | "converted" = "active",
): Promise<{ items: TradePlan[] }> {
  return unwrapResponse(
    api.get<ApiResponse<{ items: TradePlan[] }>>("/journal/plans", { params: { status } }),
  );
}

export async function deleteTradePlan(id: string): Promise<null> {
  return unwrapResponse(api.delete<ApiResponse<null>>(`/journal/plans/${id}`));
}

export async function listTradingRules(): Promise<{ items: TradingRule[] }> {
  return unwrapResponse(api.get<ApiResponse<{ items: TradingRule[] }>>("/journal/rules"));
}

export async function createTradingRule(req: {
  name: string;
  rule_type: TradingRuleType;
  threshold?: number | null;
  weight: TradingRuleWeight;
}): Promise<TradingRule> {
  return unwrapResponse(api.post<ApiResponse<TradingRule>>("/journal/rules", req));
}

export async function setTradingRuleActive(id: string, active: boolean): Promise<TradingRule> {
  return unwrapResponse(
    api.patch<ApiResponse<TradingRule>>(`/journal/rules/${id}`, { active }),
  );
}

export async function deleteTradingRule(id: string): Promise<null> {
  return unwrapResponse(api.delete<ApiResponse<null>>(`/journal/rules/${id}`));
}

export async function checkTradeCompliance(
  req: ComplianceCheckRequest,
): Promise<ComplianceSummary> {
  return unwrapResponse(
    api.post<ApiResponse<ComplianceSummary>>("/journal/compliance/check", req),
  );
}

export async function batchCreateTrades(trades: CreateTradeRequest[]): Promise<Trade[]> {
  return unwrapResponse(api.post<ApiResponse<Trade[]>>("/journal/trades/batch", { trades }));
}

export async function fetchTradeStats(params?: {
  date_from?: string; date_to?: string;
}): Promise<TradeStats> {
  return unwrapResponse(api.get<ApiResponse<TradeStats>>("/journal/stats", { params }));
}

export async function fetchTradeCalendarSummary(month: string): Promise<JournalCalendarSummary> {
  return unwrapResponse(
    api.get<ApiResponse<JournalCalendarSummary>>("/journal/calendar", {
      params: { month },
    })
  );
}

export type JournalCurrencyCode =
  | "CNY"
  | "USD"
  | "HKD"
  | "EUR"
  | "GBP"
  | "JPY"
  | "USDT";

export interface JournalSettings {
  starting_capital: number | null;
  currency_code: JournalCurrencyCode | null;
}

export async function fetchJournalSettings(): Promise<JournalSettings> {
  return unwrapResponse(api.get<ApiResponse<JournalSettings>>("/journal/settings"));
}

export async function updateJournalSettings(
  updates: Partial<JournalSettings>,
): Promise<JournalSettings> {
  return unwrapResponse(
    api.patch<ApiResponse<JournalSettings>>("/journal/settings", updates),
  );
}

export async function getDailyReview(date: string): Promise<DailyReview> {
  return unwrapResponse(api.get<ApiResponse<DailyReview>>(`/journal/reviews/${date}`));
}

export async function saveDailyReview(
  date: string,
  draft: DailyReviewDraft,
): Promise<DailyReview> {
  return unwrapResponse(api.put<ApiResponse<DailyReview>>(`/journal/reviews/${date}`, draft));
}

export async function getDailyReviewBundle(
  date: string,
  params: { date_from: string; date_to: string },
): Promise<DailyReviewBundle> {
  return unwrapResponse(
    api.get<ApiResponse<DailyReviewBundle>>(`/journal/reviews/${date}/bundle`, {
      params,
    }),
  );
}

export async function assistDailyReview(
  date: string,
  req: {
    action: DailyReviewAssistAction;
    body: string;
    selection?: string;
    date_from: string;
    date_to: string;
    lang?: string;
  },
): Promise<DailyReviewAssistResponse> {
  return unwrapResponse(
    api.post<ApiResponse<DailyReviewAssistResponse>>(`/journal/reviews/${date}/assist`, req),
  );
}

export async function exportTrades(format: "csv" | "json" = "csv"): Promise<Blob> {
  const resp = await api.get("/journal/export", { params: { format }, responseType: "blob" });
  return resp.data;
}

export async function parseFile(file: File): Promise<RecognitionResult> {
  const form = new FormData();
  form.append("file", file);
  return unwrapResponse(api.post<ApiResponse<RecognitionResult>>("/recognition/parse", form));
}

export async function createDiagnosisJob(params: {
  lang: string; date_from?: string; date_to?: string;
}): Promise<JournalJobStatus> {
  return unwrapResponse(api.post<ApiResponse<JournalJobStatus>>("/journal/diagnosis", params));
}

export async function getDiagnosisJob(jobId: string): Promise<JournalJobStatus | null> {
  return unwrapResponse(api.get<ApiResponse<JournalJobStatus | null>>(`/journal/diagnosis/${jobId}`));
}

// ── Assistant Chat API ─────────────────────────────────

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  pinned_at: string | null;
  sort_order: number;
}

export interface AgentWorkItem {
  id: string;
  kind: "tool" | "reasoning";
  status: "running" | "completed" | "pending_approval" | "failed";
  title?: string;
  tool_name?: string;
  input?: string;
  output?: string | null;
  content?: string;
  started_at: string;
  completed_at?: string | null;
}

export interface AgentWorkLog {
  status: "running" | "completed" | "interrupted" | "error" | "expired";
  started_at: string;
  completed_at?: string | null;
  duration_ms: number;
  items: AgentWorkItem[];
}

export interface MarketCandle {
  datetime: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface MarketSnapshotArtifactData {
  provider?: string;
  asset_class?: "stock" | "forex" | "crypto" | "futures" | string;
  symbol?: string;
  exchange?: string | null;
  currency?: string | null;
  interval?: string;
  as_of?: string | null;
  fetched_at?: string | null;
  quote?: {
    price?: number | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    previous_close?: number | null;
    change?: number | null;
    percent_change?: number | null;
    volume?: number | null;
  };
  technicals?: {
    sma20?: number | null;
    sma50?: number | null;
    rsi14?: number | null;
    atr14?: number | null;
    high20?: number | null;
    low20?: number | null;
  };
  recent_candles?: MarketCandle[];
  warnings?: string[];
  error?: string;
}

export interface OpportunityCheckArtifactData {
  verdict?: "compliant" | "adjust" | "insufficient_data";
  market?: MarketSnapshotArtifactData;
  opportunity?: {
    market: string;
    symbol: string;
    direction: "long" | "short";
    interval: string;
    entry_price: number | null;
    stop_loss: number | null;
    target_price: number | null;
    quantity: number | null;
    current_price: number | null;
    entry_deviation: number | null;
    entry_deviation_percent: number | null;
  };
  risk?: {
    account_size: number | null;
    unit_risk: number | null;
    risk_amount: number | null;
    risk_percent: number | null;
    reward_risk: number | null;
    max_quantity: number | null;
  };
  instrument?: Record<string, unknown> | null;
  plan_match?: {
    plan: TradePlan;
    differences: Record<string, number | null>;
  } | null;
  compliance?: ComplianceSummary;
  history?: {
    sample_count: number;
    sample_quality: "usable" | "limited" | "insufficient";
    match_fields: string[];
    wins: number;
    losses: number;
    win_rate: number | null;
    total_pnl: number | null;
    average_pnl: number | null;
    profit_factor: number | null;
    expectancy: number | null;
  };
  warnings?: string[];
  error?: string;
}

export interface AssistantArtifact {
  id: string;
  type: "market_snapshot" | "opportunity_check";
  version: 1;
  data: MarketSnapshotArtifactData | OpportunityCheckArtifactData | Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  work?: AgentWorkLog | null;
  artifacts?: AssistantArtifact[];
  attachments?: UploadedAsset[];
  created_at: string;
}

export interface AssistantInterruptPreviewLine {
  label: string;
  sub: string;
}

export interface AssistantInterruptItem {
  call_id: string;
  tool_name: string;
  action: "create" | "update" | "delete" | "tag";
  entity: "trade" | "portfolio" | "entry" | "strategy" | "memory" | "generic";
  title: string;
  preview: AssistantInterruptPreviewLine[];
}

export interface ConversationMessagePage {
  messages: ChatMessage[];
  pending: {
    items: AssistantInterruptItem[];
    work: AgentWorkLog;
    pending_at: string | null;
    expires_at: string | null;
    expired: boolean;
  } | null;
  page: {
    limit: number;
    offset: number;
    has_more: boolean;
    next_offset: number | null;
  };
}

export type AssistantAgentMode = "quick" | "standard" | "research";

export interface AssistantRunOptions {
  mode: AssistantAgentMode;
  webSearch: boolean;
}

export interface AssistantCapabilities {
  web_search: {
    available: boolean;
    provider: string | null;
  };
  vision: {
    available: boolean;
    max_images: number;
    mime_types: string[];
  };
  commands?: string[];
  market_data?: Record<string, {
    configured: boolean;
    provider: string | null;
  }>;
}

export async function getAssistantCapabilities(): Promise<AssistantCapabilities> {
  return unwrapResponseSilent(
    api.get<ApiResponse<AssistantCapabilities>>("/chat/capabilities"),
  );
}

export async function optimizeAssistantPrompt(
  content: string,
): Promise<string> {
  const result = await unwrapResponse(
    api.post<ApiResponse<{ optimized: string }>>("/chat/optimize", { content }),
  );
  return result.optimized;
}

export async function listConversations(): Promise<Conversation[]> {
  return unwrapResponse(
    api.get<ApiResponse<Conversation[]>>("/chat/conversations"),
  );
}

export async function createConversation(): Promise<Conversation> {
  return unwrapResponse(
    api.post<ApiResponse<Conversation>>("/chat/conversations"),
  );
}

export async function updateConversation(
  conversationId: string,
  params: { title?: string; pinned?: boolean },
): Promise<Conversation> {
  return unwrapResponse(
    api.patch<ApiResponse<Conversation>>(
      `/chat/conversations/${conversationId}`,
      params,
    ),
  );
}

export async function reorderConversations(
  conversationIds: string[],
): Promise<Conversation[]> {
  return unwrapResponse(
    api.put<ApiResponse<Conversation[]>>("/chat/conversations/order", {
      conversation_ids: conversationIds,
    }),
  );
}

export async function getConversationMessages(
  conversationId: string,
  limit = 100,
  offset = 0,
): Promise<ConversationMessagePage> {
  return unwrapResponse(
    api.get<ApiResponse<ConversationMessagePage>>(
      `/chat/conversations/${conversationId}/messages`,
      { params: { limit, offset } },
    ),
  );
}

export async function deleteConversation(
  conversationId: string,
): Promise<{ deleted: boolean }> {
  return unwrapResponse(
    api.delete<ApiResponse<{ deleted: boolean }>>(
      `/chat/conversations/${conversationId}`,
    ),
  );
}

/**
 * Returns the URL for the SSE send endpoint (streaming uses fetch, not Axios).
 * The caller must attach auth + content-type headers.
 */
export function assistantMessageUrl(conversationId: string): string {
  const baseURL = api.defaults.baseURL || "/api";
  return `${baseURL}/chat/conversations/${conversationId}/messages`;
}

export function assistantReplaceLastMessageUrl(conversationId: string): string {
  const baseURL = api.defaults.baseURL || "/api";
  return `${baseURL}/chat/conversations/${conversationId}/messages/last`;
}

export function assistantResumeUrl(conversationId: string): string {
  const baseURL = api.defaults.baseURL || "/api";
  return `${baseURL}/chat/conversations/${conversationId}/resume`;
}

// ─── Auth API ─────────────────────────────────────────

export interface AuthResponse {
  token: string;
  user: User;
}

export interface MfaLoginChallenge {
  token: string;
  expires_in: number;
}

export type AuthLoginResult =
  | ({ mfa_required: false } & AuthResponse)
  | { mfa_required: true; challenge: MfaLoginChallenge };

export interface GoogleAuthConfig {
  enabled: boolean;
  client_id: string | null;
}

export interface MfaStatus {
  enabled: boolean;
  enabled_at: string | null;
  recovery_codes_remaining: number;
}

export interface MfaSetup {
  otpauth_uri: string;
  manual_key: string;
}

export interface MfaEnrollmentResponse extends AuthResponse {
  recovery_codes: string[];
}

export async function authRegister(params: {
  email: string;
  password: string;
  name?: string;
}): Promise<AuthResponse> {
  return unwrapResponse(api.post<ApiResponse<AuthResponse>>("/auth/register", params));
}

export async function authLogin(params: {
  email: string;
  password: string;
}): Promise<AuthLoginResult> {
  return unwrapResponse(api.post<ApiResponse<AuthLoginResult>>("/auth/login", params));
}

export async function authGoogleConfig(): Promise<GoogleAuthConfig> {
  return unwrapResponse(
    api.get<ApiResponse<GoogleAuthConfig>>("/auth/google/config"),
  );
}

export async function authGoogleLogin(credential: string): Promise<AuthLoginResult> {
  return unwrapResponse(
    api.post<ApiResponse<AuthLoginResult>>("/auth/google", { credential }),
  );
}

export async function authVerifyMfaLogin(params: {
  challenge_token: string;
  code: string;
}): Promise<AuthResponse> {
  return unwrapResponse(
    api.post<ApiResponse<AuthResponse>>("/auth/mfa/login/verify", params),
  );
}

export async function authMe(): Promise<User> {
  return unwrapResponse(api.get<ApiResponse<User>>("/auth/me"));
}

export async function authUpdateProfile(params: { name: string }): Promise<User> {
  return unwrapResponse(api.put<ApiResponse<User>>("/auth/profile", params));
}

export async function authChangePassword(params: {
  current_password?: string;
  new_password: string;
}): Promise<AuthResponse> {
  return unwrapResponse(
    api.put<ApiResponse<AuthResponse>>("/auth/password", params),
  );
}

export async function authMfaStatus(): Promise<MfaStatus> {
  return unwrapResponse(api.get<ApiResponse<MfaStatus>>("/auth/mfa/status"));
}

export async function authStartMfaSetup(params: {
  current_password: string;
}): Promise<MfaSetup> {
  return unwrapResponse(
    api.post<ApiResponse<MfaSetup>>("/auth/mfa/setup/start", params),
  );
}

export async function authConfirmMfaSetup(params: {
  code: string;
}): Promise<MfaEnrollmentResponse> {
  return unwrapResponse(
    api.post<ApiResponse<MfaEnrollmentResponse>>(
      "/auth/mfa/setup/confirm",
      params,
    ),
  );
}

export async function authDisableMfa(params: {
  current_password: string;
  code: string;
}): Promise<AuthResponse> {
  return unwrapResponse(
    api.post<ApiResponse<AuthResponse>>("/auth/mfa/disable", params),
  );
}

export async function authRegenerateMfaRecoveryCodes(params: {
  current_password: string;
  code: string;
}): Promise<string[]> {
  const result = await unwrapResponse(
    api.post<ApiResponse<{ recovery_codes: string[] }>>(
      "/auth/mfa/recovery-codes/regenerate",
      params,
    ),
  );
  return result.recovery_codes;
}

export async function authDeleteAccount(params: {
  current_password: string;
}): Promise<void> {
  await unwrapResponse(
    api.delete<ApiResponse<{ deleted: boolean }>>("/auth/account", {
      data: params,
    }),
  );
}

// ─── Billing API ─────────────────────────────────────────

export type BillingFeature =
  | "assistant.basic"
  | "assistant.research"
  | "assistant.web_search"
  | "assistant.vision"
  | "assistant.optimize"
  | "analysis.run"
  | "journal.ai_assist"
  | "recognition.parse";

export interface BillingUsage {
  metric: "ai_units";
  used: number;
  limit: number;
  remaining: number;
  resets_at: string;
}

export interface BillingSummary {
  plan: "free" | "pro";
  status: string;
  billing_interval: "month" | "year" | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  features: Record<BillingFeature, boolean>;
  usage: BillingUsage;
  stripe_configured: boolean;
  prices: {
    currency: string;
    monthly: number;
    yearly: number;
  };
}

export async function fetchBillingSummary(): Promise<BillingSummary> {
  return unwrapResponseSilent(api.get<ApiResponse<BillingSummary>>("/billing/me"));
}

export async function createBillingCheckout(
  interval: "month" | "year",
): Promise<{ url: string }> {
  return unwrapResponse(
    api.post<ApiResponse<{ url: string }>>("/billing/checkout-session", { interval }),
  );
}

export async function createBillingPortal(): Promise<{ url: string }> {
  return unwrapResponse(
    api.post<ApiResponse<{ url: string }>>("/billing/portal-session"),
  );
}

// ── Backtest API ─────────────────────────────────────────

export interface StrategyCondition {
  left: { type: string; params?: Record<string, number>; field?: string };
  operator: string;
  right: { type: string; params?: Record<string, number>; field?: string; value?: number };
}

export interface StrategyConditionGroup {
  operator: "and" | "or";
  conditions: StrategyCondition[];
}

export interface StrategyConfig {
  schema_version?: 2;
  symbol: string;
  series_id?: string;
  interval: string;
  direction: "long" | "short";
  entry_groups_operator: "and" | "or";
  entry_groups: StrategyConditionGroup[];
  exit_groups_operator: "and" | "or";
  exit_groups: StrategyConditionGroup[];
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  trailing_stop_pct: number | null;
  breakeven_trigger_pct: number | null;
  max_holding_bars: number | null;
  lookback_months: number;
  initial_cash: number;
  position_size: number;
  commission_bps: number;
  spread_bps: number;
}

export interface Strategy {
  id: string;
  name: string;
  config: StrategyConfig;
  created_at: string;
  updated_at: string;
}

export interface BacktestStats {
  total_pnl: number;
  total_return_pct?: number;
  annualized_return_pct?: number;
  exposure_pct?: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number | null;
  max_drawdown: number;
  max_drawdown_pct?: number;
  max_drawdown_duration?: string | null;
  sharpe_ratio: number;
  avg_trade_duration?: string | null;
  commission_paid?: number;
  avg_win: number;
  avg_loss: number;
  win_loss_ratio: number;
}

export interface BacktestResult extends BacktestStats {
  engine: {
    name: string;
    version: string;
    execution: string;
  };
  assumptions: {
    initial_cash: number;
    position_size: number;
    commission_bps: number;
    spread_bps: number;
  };
  market_data?: {
    series_id: string;
    provider: string;
    provider_symbol: string;
    provider_exchange: string | null;
    cache_status: "miss" | "hit" | "stale";
    requested_start: string;
    requested_end: string;
    actual_start: string;
    actual_end: string;
    quality_status: "ok" | "warning";
    quality_warnings: string[];
  };
  equity_curve: { time: string; equity: number }[];
  drawdown_curve?: {
    time: string;
    drawdown: number;
    drawdown_pct: number;
  }[];
  price_curve?: {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
  }[];
  benchmark?: {
    start_price: number;
    end_price: number;
    return_pct: number;
    total_pnl: number;
  };
  trades: {
    entry_time: string;
    exit_time: string;
    direction: "long" | "short";
    entry_price: number;
    exit_price: number;
    size: number;
    pnl: number;
    commission: number;
    return_pct: number;
    exit_reason:
      | "stop_loss"
      | "take_profit"
      | "trailing_stop"
      | "breakeven"
      | "time_exit"
      | "condition_or_end";
  }[];
}

export interface CompactBacktestMetrics {
  total_return_pct: number;
  total_pnl: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number | null;
  max_drawdown_pct: number;
  sharpe_ratio: number;
}

export interface OptimizationResult {
  kind: "optimization";
  objective: string;
  trial_count: number;
  best_parameters: Record<string, number>;
  best_result: BacktestResult;
  trials: {
    parameters: Record<string, number>;
    metrics: CompactBacktestMetrics;
  }[];
}

export interface ValidationResult {
  kind: "validation";
  train_ratio: number;
  split_time: string;
  train_result: BacktestResult;
  test_result: BacktestResult;
  degradation: {
    total_return_pct: number;
    sharpe_ratio: number;
    win_rate: number;
  };
}

export interface WalkForwardResult {
  kind: "walk_forward";
  objective: string;
  train_bars: number;
  test_bars: number;
  step_bars: number;
  window_count: number;
  summary: {
    average_test_return_pct: number;
    compounded_test_return_pct: number;
    profitable_windows: number;
    total_trades: number;
  };
  windows: {
    train_start: string;
    train_end: string;
    test_start: string;
    test_end: string;
    best_parameters: Record<string, number>;
    train_metrics: CompactBacktestMetrics;
    test_metrics: CompactBacktestMetrics;
  }[];
}

export type BacktestAnalysisResult =
  | OptimizationResult
  | ValidationResult
  | WalkForwardResult;
export type BacktestRunResult = BacktestResult | BacktestAnalysisResult;

export interface BacktestJobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: BacktestResult | null;
  error?: string | null;
  created_at?: string;
}

export interface BacktestRun {
  id: string;
  run_id: string;
  job_id: string;
  strategy_id: string | null;
  strategy_name: string;
  strategy_config: StrategyConfig;
  run_kind: "standard" | "optimization" | "validation" | "walk_forward";
  analysis_config: Record<string, unknown> | null;
  status: "queued" | "running" | "completed" | "failed";
  requested_date_from: string | null;
  requested_date_to: string | null;
  actual_date_from: string | null;
  actual_date_to: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  result?: BacktestRunResult | null;
}

export interface MarketInstrumentMatch {
  series_id: string;
  symbol: string;
  name: string;
  asset_class: string;
  venue: string | null;
  series_kind: string | null;
}

export async function searchMarketInstruments(
  query: string,
  assetClass?: string,
): Promise<MarketInstrumentMatch[]> {
  const response = await unwrapResponse(
    api.get<ApiResponse<{ items: MarketInstrumentMatch[] }>>(
      "/market/instruments",
      { params: { q: query, asset_class: assetClass } },
    ),
  );
  return response.items;
}

export async function createStrategy(params: { name: string; config: StrategyConfig }): Promise<Strategy> {
  return unwrapResponse(api.post<ApiResponse<Strategy>>("/backtest/strategies", params));
}
export async function listStrategies(): Promise<Strategy[]> {
  return unwrapResponse(api.get<ApiResponse<Strategy[]>>("/backtest/strategies"));
}
export async function updateStrategy(id: string, params: { name?: string; config?: StrategyConfig }): Promise<Strategy> {
  return unwrapResponse(api.put<ApiResponse<Strategy>>(`/backtest/strategies/${id}`, params));
}
export async function deleteStrategy(id: string): Promise<{ deleted: boolean }> {
  return unwrapResponse(api.delete<ApiResponse<{ deleted: boolean }>>(`/backtest/strategies/${id}`));
}
export async function createBacktestRun(params: {
  strategy_id: string;
  date_from?: string | null;
  date_to?: string | null;
}): Promise<BacktestRun> {
  return unwrapResponse(api.post<ApiResponse<BacktestRun>>("/backtest/runs", params));
}
export async function createOptimizationRun(params: {
  strategy_id: string;
  date_from?: string | null;
  date_to?: string | null;
  objective: string;
  grids: { parameter: string; values: number[] }[];
}): Promise<BacktestRun> {
  return unwrapResponse(
    api.post<ApiResponse<BacktestRun>>("/backtest/runs/optimization", params),
  );
}
export async function createValidationRun(params: {
  strategy_id: string;
  date_from?: string | null;
  date_to?: string | null;
  train_ratio: number;
}): Promise<BacktestRun> {
  return unwrapResponse(
    api.post<ApiResponse<BacktestRun>>("/backtest/runs/validation", params),
  );
}
export async function createWalkForwardRun(params: {
  strategy_id: string;
  date_from?: string | null;
  date_to?: string | null;
  objective: string;
  grids: { parameter: string; values: number[] }[];
  train_bars: number;
  test_bars: number;
  step_bars: number;
}): Promise<BacktestRun> {
  return unwrapResponse(
    api.post<ApiResponse<BacktestRun>>("/backtest/runs/walk-forward", params),
  );
}
export async function listBacktestRuns(params?: {
  strategy_id?: string;
  status?: BacktestRun["status"];
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<BacktestRun>> {
  return unwrapResponse(
    api.get<ApiResponse<PaginatedResponse<BacktestRun>>>("/backtest/runs", {
      params,
    }),
  );
}
export async function getBacktestRun(runId: string): Promise<BacktestRun> {
  return unwrapResponse(
    api.get<ApiResponse<BacktestRun>>(`/backtest/runs/${runId}`),
  );
}
export async function rerunBacktest(runId: string): Promise<BacktestRun> {
  return unwrapResponse(
    api.post<ApiResponse<BacktestRun>>(`/backtest/runs/${runId}/rerun`),
  );
}
export async function deleteBacktestRun(runId: string): Promise<void> {
  await unwrapResponse(
    api.delete<ApiResponse<null>>(`/backtest/runs/${runId}`),
  );
}

export async function runBacktest(params: {
  strategy_id: string;
  date_from?: string | null;
  date_to?: string | null;
}): Promise<BacktestRun> {
  return createBacktestRun(params);
}
export async function getBacktestJob(jobId: string): Promise<BacktestRun> {
  return getBacktestRun(jobId);
}

// ─── Replay API ───────────────────────────────────────────

export interface ReplayBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ReplayBundle {
  trade: {
    id: string;
    symbol: string;
    exchange: string | null;
    direction: "long" | "short";
    open_time: string;
    close_time: string | null;
    open_price: number | null;
    close_price: number | null;
    pnl: number | null;
  };
  instrument: {
    series_id: string;
    display_symbol: string;
    venue: string | null;
    fidelity: "exact" | "reference";
  };
  meta: {
    requested_interval: string;
    interval: string;
    window: "compact" | "standard" | "full";
    series_id: string;
    data_source: string;
    cache_status: "miss" | "hit" | "stale";
    quality_warnings: string[];
    coverage_start: string;
    coverage_end: string;
    bar_count: number;
    start_index: number;
    decision_index: number;
  };
  bars: ReplayBar[];
  open_index: number;
  close_index: number | null;
}

export type ReplayProblemCode =
  | "trade_not_found"
  | "missing_open_time"
  | "invalid_trade_time"
  | "instrument_required"
  | "interval_unavailable"
  | "coverage_unavailable"
  | "provider_unavailable"
  | "invalid_market_data"
  | "unknown";

export interface ReplayApiProblem {
  problem: ReplayProblemCode;
  retryable: boolean;
  suggested_intervals: string[];
}

export class ReplayApiError extends Error {
  problem: ReplayApiProblem;

  constructor(problem: ReplayApiProblem) {
    super(problem.problem);
    this.name = "ReplayApiError";
    this.problem = problem;
  }
}

export async function fetchReplayBundle(
  tradeId: string,
  params: { interval: string; window: "compact" | "standard" | "full" },
): Promise<ReplayBundle> {
  try {
    const { data } = await api.get<ApiResponse<ReplayBundle>>(
      `/replay/${tradeId}`,
      { params },
    );
    return data.data;
  } catch (error) {
    if (axios.isAxiosError<ApiResponse<ReplayApiProblem>>(error)) {
      const problem = error.response?.data?.data;
      if (problem?.problem) throw new ReplayApiError(problem);
    }
    throw new ReplayApiError({
      problem: "unknown",
      retryable: true,
      suggested_intervals: [],
    });
  }
}

// ─── Journal Batch Ops ───────────────────────────────────

export interface TradeFilterParams {
  symbol?: string;
  direction?: string;
  position_status?: "open" | "closed";
  tag?: string;
  date_from?: string;
  date_to?: string;
}

export type BatchTarget =
  | { trade_ids: string[] }
  | { select_all_matching: true; filter: TradeFilterParams };

export async function batchDeleteTrades(target: BatchTarget): Promise<{ deleted: number }> {
  return unwrapResponse(
    api.post<ApiResponse<{ deleted: number }>>("/journal/trades/batch/delete", target),
  );
}

export async function batchAddTags(
  target: BatchTarget,
  tags: string[],
): Promise<{ updated: number }> {
  return unwrapResponse(
    api.post<ApiResponse<{ updated: number }>>(
      "/journal/trades/batch/tag",
      { ...target, tags },
    ),
  );
}

export async function exportTradesSelected(
  target: BatchTarget,
  format: "csv" | "json" = "csv",
): Promise<Blob> {
  const response = await api.post(
    "/journal/trades/export",
    { ...target, format },
    { responseType: "blob" },
  );
  return response.data as Blob;
}

// ─── Portfolio Types (by-currency redesign) ──────────────────

export interface Portfolio {
  id: string;
  name: string;
  currency: string;
  entry_count: number;
  created_at: string;
  updated_at: string;
}

export interface PortfolioEntry {
  id: string;
  portfolio_id: string;
  name: string;
  category: string;
  platform: string | null;
  amount: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface PortfolioCategory {
  id: string;
  name: string;
  kind: "asset" | "liability";
  sort_order: number;
  is_preset: boolean;
}

export interface CreatePortfolioRequest {
  name: string;
  currency: string;
}

export interface UpdatePortfolioRequest {
  name?: string;
  currency?: string;
}

export interface CreatePortfolioEntryRequest {
  name: string;
  category: string;
  amount: number;
  platform?: string | null;
  notes?: string;
}

export interface UpdatePortfolioEntryRequest {
  name?: string;
  category?: string;
  amount?: number;
  platform?: string | null;
  notes?: string;
}

export interface PortfolioSummary {
  portfolio: { id: string; name: string; currency: string };
  totals: { assets: number; liabilities: number; net_worth: number };
  by_category: { name: string; kind: "asset" | "liability"; total: number; count: number }[];
  by_platform: { name: string; total: number; count: number }[];
}

export interface PortfolioEntryFilter {
  category?: string;
  platform?: string;
  search?: string;
  sort?: string;
}

export interface PortfolioImportResult {
  inserted: number;
  skipped: number;
  errors: { row: number; reason: string }[];
}

// ─── Portfolio API ───────────────────────────────────────────

export async function listPortfolios(): Promise<{ items: Portfolio[] }> {
  return unwrapResponse(api.get<ApiResponse<{ items: Portfolio[] }>>("/portfolio/portfolios"));
}

export async function createPortfolio(req: CreatePortfolioRequest): Promise<Portfolio> {
  return unwrapResponse(api.post<ApiResponse<Portfolio>>("/portfolio/portfolios", req));
}

export async function updatePortfolio(id: string, req: UpdatePortfolioRequest): Promise<Portfolio> {
  return unwrapResponse(api.patch<ApiResponse<Portfolio>>(`/portfolio/portfolios/${id}`, req));
}

export async function deletePortfolio(
  id: string,
): Promise<{ deleted: boolean; deleted_entries: number }> {
  return unwrapResponse(
    api.delete<ApiResponse<{ deleted: boolean; deleted_entries: number }>>(
      `/portfolio/portfolios/${id}`,
    ),
  );
}

export async function getPortfolioSummary(portfolioId: string): Promise<PortfolioSummary> {
  return unwrapResponse(
    api.get<ApiResponse<PortfolioSummary>>(`/portfolio/portfolios/${portfolioId}/summary`),
  );
}

export async function listPortfolioEntries(
  portfolioId: string,
  filter: PortfolioEntryFilter = {},
): Promise<{ items: PortfolioEntry[] }> {
  return unwrapResponse(
    api.get<ApiResponse<{ items: PortfolioEntry[] }>>(
      `/portfolio/portfolios/${portfolioId}/entries`,
      { params: filter },
    ),
  );
}

export async function createPortfolioEntry(
  portfolioId: string,
  req: CreatePortfolioEntryRequest,
): Promise<PortfolioEntry> {
  return unwrapResponse(
    api.post<ApiResponse<PortfolioEntry>>(
      `/portfolio/portfolios/${portfolioId}/entries`,
      req,
    ),
  );
}

export async function updatePortfolioEntry(
  id: string,
  req: UpdatePortfolioEntryRequest,
): Promise<PortfolioEntry> {
  return unwrapResponse(
    api.patch<ApiResponse<PortfolioEntry>>(`/portfolio/entries/${id}`, req),
  );
}

export async function deletePortfolioEntry(id: string): Promise<{ deleted: boolean }> {
  return unwrapResponse(
    api.delete<ApiResponse<{ deleted: boolean }>>(`/portfolio/entries/${id}`),
  );
}

export async function batchDeletePortfolioEntries(ids: string[]): Promise<{ deleted: number }> {
  return unwrapResponse(
    api.post<ApiResponse<{ deleted: number }>>("/portfolio/entries/batch/delete", { ids }),
  );
}

export async function listPortfolioCategories(): Promise<{ items: PortfolioCategory[] }> {
  return unwrapResponse(
    api.get<ApiResponse<{ items: PortfolioCategory[] }>>("/portfolio/categories"),
  );
}

export async function createPortfolioCategory(
  name: string,
  kind: "asset" | "liability",
): Promise<PortfolioCategory> {
  return unwrapResponse(
    api.post<ApiResponse<PortfolioCategory>>("/portfolio/categories", { name, kind }),
  );
}

export async function deletePortfolioCategory(id: string): Promise<{ deleted: boolean }> {
  return unwrapResponse(
    api.delete<ApiResponse<{ deleted: boolean }>>(`/portfolio/categories/${id}`),
  );
}

export async function exportPortfolio(portfolioId: string): Promise<Blob> {
  const r = await api.get(`/portfolio/portfolios/${portfolioId}/entries/export`, {
    responseType: "blob",
  });
  return r.data as Blob;
}

export async function importPortfolio(
  portfolioId: string,
  file: File,
): Promise<PortfolioImportResult> {
  const form = new FormData();
  form.append("file", file);
  return unwrapResponse(
    api.post<ApiResponse<PortfolioImportResult>>(
      `/portfolio/portfolios/${portfolioId}/entries/import`,
      form,
    ),
  );
}

// ─── Market Overview API ───────────────────────────────────

export interface MarketOverviewQuote {
  symbol: string;
  label: string;
  group?: "indices" | "rates" | "energy" | "metals" | "forex" | "crypto";
  price: number | null;
  change: number | null;
  percent_change: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
  currency: string | null;
  exchange: string | null;
  as_of: string | null;
  sparkline?: Array<{ time: string; price: number }>;
}

export interface MarketOverviewMacro {
  series_id: string;
  label: string;
  latest?: { date: string; value: number } | null;
  previous?: { date: string; value: number } | null;
  error?: string;
}

export interface MarketOverviewCalendarEvent {
  title: string | null;
  currency: string | null;
  date: string;
  impact: "medium" | "high";
  actual: string | null;
  forecast: string | null;
  previous: string | null;
}

export interface MarketOverview {
  quotes: {
    provider: string;
    items: MarketOverviewQuote[];
    error?: string;
  };
  macro: MarketOverviewMacro[];
  states: {
    risk: "risk_on" | "risk_off" | null;
    equities: "up" | "down" | null;
    crypto: "up" | "down" | null;
    dollar: "stronger" | "weaker" | null;
    gold: "up" | "down" | null;
  };
  cache?: {
    status: "fresh" | "stale";
    fetched_at: string;
  };
}

export interface EconomicCalendarData {
  provider: string;
  source_url?: string;
  fetched_at?: string;
  items: MarketOverviewCalendarEvent[];
  error?: string;
}

export type MarketBriefingBias = "bullish" | "bearish" | "neutral";
export type MarketBriefingVolatility = "low" | "normal" | "elevated" | "event_driven";
export type MarketBriefingRisk = "risk_on" | "risk_off" | "mixed";
export type MarketBriefingConfidence = "high" | "medium" | "low";

export interface DailyMarketBriefing {
  generated_at: string;
  market_as_of: string | null;
  model: string;
  summary: string;
  regime: {
    bias: MarketBriefingBias;
    volatility: MarketBriefingVolatility;
    risk: MarketBriefingRisk;
    confidence: MarketBriefingConfidence;
  };
  drivers: Array<{
    label: string;
    direction: "supportive" | "restrictive" | "mixed";
    detail: string;
  }>;
  catalysts: Array<{
    title: string;
    currency: string | null;
    date: string;
    impact: "medium" | "high";
    actual: string | null;
    forecast: string | null;
    previous: string | null;
    source_url: string | null;
  }>;
  news: Array<{
    title: string;
    summary: string;
    source: string;
    url: string;
    published_at: string | null;
    related: string;
  }>;
  playbook: {
    bullish: string;
    bearish: string;
    no_trade: string;
  };
  sources: Array<{
    name: string;
    kind: "market" | "macro" | "calendar" | "news";
    url: string | null;
    as_of: string | null;
  }>;
}

export async function fetchMarketOverview(
  forceRefresh = false,
  silent = false,
): Promise<MarketOverview> {
  const request = api.get<ApiResponse<MarketOverview>>("/market/overview", {
    params: forceRefresh ? { force_refresh: true } : undefined,
  });
  return silent ? unwrapResponseSilent(request) : unwrapResponse(request);
}

export async function fetchEconomicCalendar(): Promise<EconomicCalendarData> {
  return unwrapResponse(
    api.get<ApiResponse<EconomicCalendarData>>("/market/economic-calendar"),
  );
}

export async function fetchDailyMarketBriefing(
  lang: "zh" | "en",
  forceRefresh = false,
): Promise<DailyMarketBriefing> {
  return unwrapResponse(
    api.get<ApiResponse<DailyMarketBriefing>>("/market/daily-briefing", {
      params: { lang, force_refresh: forceRefresh },
    }),
  );
}

export interface LocalizedMarketText {
  zh: string;
  en: string;
}

export type MarketHoursSessionKind = "main" | "night" | "pre" | "after";
export type MarketHoursState = MarketHoursSessionKind | "closed";
export type MarketHoursGroup = "equities" | "spot_forex" | "futures" | "forex_session";

export interface MarketHoursSession {
  kind: MarketHoursSessionKind;
  start_at: string;
  end_at: string;
}

export interface MarketHoursItem {
  id: string;
  group: MarketHoursGroup;
  name: LocalizedMarketText;
  city: LocalizedMarketText;
  country_code: string;
  timezone: string;
  state: MarketHoursState;
  next_transition_at: string | null;
  note?: LocalizedMarketText | null;
  sessions: MarketHoursSession[];
  notification_capabilities: string[];
}

export interface MarketHoursOverlap {
  id: "tokyo_london" | "london_new_york";
  sessions: Array<{ start_at: string; end_at: string }>;
}

export interface MarketHours {
  generated_at: string;
  schedule_version: string;
  reference_timezone: string;
  reference_date: string;
  window_start_at: string;
  window_end_at: string;
  active_count: number;
  markets: MarketHoursItem[];
  forex_sessions: MarketHoursItem[];
  forex_overlaps: MarketHoursOverlap[];
  calendar_notice: LocalizedMarketText;
}

export async function fetchMarketHours(
  referenceTimezone: string,
  silent = false,
): Promise<MarketHours> {
  const request = api.get<ApiResponse<MarketHours>>("/market/hours", {
    params: { timezone: referenceTimezone },
  });
  return silent ? unwrapResponseSilent(request) : unwrapResponse(request);
}

// ─── Radar Feed API ──────────────────────────────────────────

export type NotificationChannelStatus = "pending" | "active" | "disabled";

export interface NotificationChannel {
  id: string;
  channel_type: string;
  name: string;
  status: NotificationChannelStatus;
  address: string | null;
  metadata: Record<string, unknown>;
  locale: "zh" | "en";
  last_error_code: string | null;
  last_error_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationSubscription {
  id: string;
  channel_id: string;
  event_type: string;
  subject_type: string | null;
  subject_id: string | null;
  enabled: boolean;
  locale: "zh" | "en";
  created_at: string;
  updated_at: string;
}

export interface NotificationDelivery {
  id: string;
  event_type: string;
  subject_type: string | null;
  subject_id: string | null;
  title: string;
  status: string;
  attempt_count: number;
  occurred_at: string;
  sent_at: string | null;
  last_error_code: string | null;
  created_at: string;
}

export interface NotificationInboxItem {
  id: string;
  event_type: string;
  subject_type: string | null;
  subject_id: string | null;
  title: string;
  body: string;
  action_url: string | null;
  occurred_at: string;
  created_at: string;
  read_at: string | null;
}

export interface NotificationInboxPage {
  items: NotificationInboxItem[];
  next_cursor: string | null;
  unread_count: number;
}

export interface TelegramConnectResult {
  channel_id: string;
  deep_link: string;
  expires_at: string;
}

export interface NotificationSubscriptionRequest {
  channel_id: string;
  event_type: string;
  subject_type?: string | null;
  subject_id?: string | null;
  enabled: boolean;
  locale: "zh" | "en";
}

export async function listNotificationChannels(): Promise<NotificationChannel[]> {
  return unwrapResponse(api.get<ApiResponse<NotificationChannel[]>>("/notifications/channels"));
}

export async function connectTelegram(locale: "zh" | "en"): Promise<TelegramConnectResult> {
  return unwrapResponse(
    api.post<ApiResponse<TelegramConnectResult>>("/notifications/channels/telegram/connect", { locale }),
  );
}

export async function connectDiscord(
  webhookUrl: string,
  locale: "zh" | "en",
): Promise<NotificationChannel> {
  return unwrapResponse(
    api.post<ApiResponse<NotificationChannel>>("/notifications/channels/discord/connect", {
      webhook_url: webhookUrl,
      locale,
    }),
  );
}

export async function testNotificationChannel(channelId: string): Promise<{ ok: boolean }> {
  return unwrapResponse(
    api.post<ApiResponse<{ ok: boolean }>>(`/notifications/channels/${channelId}/test`),
  );
}

export async function deleteNotificationChannel(channelId: string): Promise<void> {
  await unwrapResponse(
    api.delete<ApiResponse<{ ok: boolean }>>(`/notifications/channels/${channelId}`),
  );
}

export async function listNotificationSubscriptions(): Promise<NotificationSubscription[]> {
  return unwrapResponse(
    api.get<ApiResponse<NotificationSubscription[]>>("/notifications/subscriptions"),
  );
}

export async function upsertNotificationSubscription(
  request: NotificationSubscriptionRequest,
): Promise<NotificationSubscription> {
  return unwrapResponse(
    api.put<ApiResponse<NotificationSubscription>>("/notifications/subscriptions", request),
  );
}

export async function listNotificationDeliveries(limit = 20): Promise<NotificationDelivery[]> {
  return unwrapResponse(
    api.get<ApiResponse<NotificationDelivery[]>>("/notifications/deliveries", { params: { limit } }),
  );
}

export async function listNotificationInbox(options?: {
  unreadOnly?: boolean;
  cursor?: string | null;
  limit?: number;
}): Promise<NotificationInboxPage> {
  return unwrapResponse(
    api.get<ApiResponse<NotificationInboxPage>>("/notifications/inbox", {
      params: {
        unread_only: options?.unreadOnly ?? false,
        cursor: options?.cursor || undefined,
        limit: options?.limit ?? 20,
      },
    }),
  );
}

export async function getNotificationInboxUnreadCount(
  silent = false,
): Promise<number> {
  const request = api.get<ApiResponse<{ count: number }>>(
    "/notifications/inbox/unread-count",
  );
  const result = silent
    ? await unwrapResponseSilent(request)
    : await unwrapResponse(request);
  return result.count;
}

export async function markNotificationInboxRead(deliveryId: string): Promise<void> {
  await unwrapResponse(
    api.post<ApiResponse<{ ok: boolean }>>(
      `/notifications/inbox/${deliveryId}/read`,
    ),
  );
}

export async function markAllNotificationInboxRead(): Promise<number> {
  const result = await unwrapResponse(
    api.post<ApiResponse<{ updated: number }>>("/notifications/inbox/read-all"),
  );
  return result.updated;
}

export async function deleteNotificationInboxMessage(deliveryId: string): Promise<void> {
  await unwrapResponse(
    api.delete<ApiResponse<{ ok: boolean }>>(
      `/notifications/inbox/${deliveryId}`,
    ),
  );
}

export interface FeedItem {
  id: string;
  url: string;
  source_key: string;
  title: string;
  summary: string;
  published_at: string | null;
  fetched_at: string;
  category: string;
  symbols: string[];
  symbol_labels: Record<string, string>;
  lang: string;
}

export interface FeedItemsResponse {
  items: FeedItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface FeedBriefingPoint {
  text: string;
  id?: string;
}

export interface FeedBriefingContent {
  hot: { title: string; sources: number; id?: string }[];
  sections: { category: string; points: FeedBriefingPoint[] }[];
}

export interface FeedBriefing {
  id: string;
  generated_at: string;
  lang: string;
  window: string;
  content: FeedBriefingContent;
  model: string;
}

export interface FeedBookmark {
  id: string;
  feed_item_id: string;
  created_at: string;
}

export interface FeedBookmarkItem extends FeedItem {
  bookmark_id: string;
  bookmarked_at: string;
}

export interface FeedBookmarkItemsResponse {
  items: FeedBookmarkItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function listFeedItems(params?: {
  page?: number; page_size?: number; category?: string;
  source?: string; lang?: string; q?: string; symbol?: string;
}): Promise<FeedItemsResponse> {
  return unwrapResponse(
    api.get<ApiResponse<FeedItemsResponse>>("/feed/items", { params }),
  );
}

/** Background-poll variant of listFeedItems: stays silent on failure. */
export async function pollFeedItems(params?: {
  page?: number; page_size?: number; category?: string;
  source?: string; lang?: string; q?: string; symbol?: string;
}): Promise<FeedItemsResponse> {
  return unwrapResponseSilent(
    api.get<ApiResponse<FeedItemsResponse>>("/feed/items", { params }),
  );
}

export async function getFeedItem(itemId: string): Promise<FeedItem> {
  return unwrapResponse(
    api.get<ApiResponse<FeedItem>>(`/feed/items/${itemId}`),
  );
}

export async function fetchLatestBriefing(lang?: string): Promise<FeedBriefing | null> {
  return unwrapResponse(
    api.get<ApiResponse<FeedBriefing | null>>("/feed/briefing/latest", {
      params: { lang },
    }),
  );
}

export async function listFeedBookmarks(): Promise<FeedBookmark[]> {
  return unwrapResponse(api.get<ApiResponse<FeedBookmark[]>>("/feed/bookmarks"));
}

export async function listFeedBookmarkItems(params?: {
  page?: number; page_size?: number;
}): Promise<FeedBookmarkItemsResponse> {
  return unwrapResponse(
    api.get<ApiResponse<FeedBookmarkItemsResponse>>("/feed/bookmarks/items", { params }),
  );
}

export async function addFeedBookmark(feedItemId: string): Promise<FeedBookmark> {
  return unwrapResponse(
    api.post<ApiResponse<FeedBookmark>>("/feed/bookmarks", { feed_item_id: feedItemId }),
  );
}

export async function removeFeedBookmark(bookmarkId: string): Promise<{ ok: boolean }> {
  return unwrapResponse(
    api.delete<ApiResponse<{ ok: boolean }>>(`/feed/bookmarks/${bookmarkId}`),
  );
}
