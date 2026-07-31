import axios from "axios";
import { API_BASE_URL } from "./base-url";

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

const api = axios.create({ baseURL: API_BASE_URL, timeout: 30000 });
api.interceptors.request.use((config) => {
  const token = window.localStorage.getItem("antitrade.auth.token");
  if (token) config.headers["Authorization"] = `Bearer ${token}`;
  return config;
});

async function unwrap<T>(p: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const { data } = await p;
  if (data.code !== 0) throw new Error(data.message || "Request failed");
  return data.data;
}

export interface Strategy {
  id: string;
  user_id: string;
  title: string;
  body: string;
  tags: string[];
  trade_count: number;
  win_rate: number | null;
  created_at: string;
  updated_at: string;
}

export interface StrategyOption {
  id: string;
  title: string;
}

export interface PatchStrategyRequest {
  title?: string;
  body?: string;
  tags?: string[];
}

export function listStrategies(): Promise<Strategy[]> {
  return unwrap(api.get<ApiResponse<Strategy[]>>("/strategies"));
}

export function listStrategyOptions(): Promise<StrategyOption[]> {
  return unwrap(api.get<ApiResponse<StrategyOption[]>>("/strategies/options"));
}

export function getStrategy(id: string): Promise<Strategy> {
  return unwrap(api.get<ApiResponse<Strategy>>(`/strategies/${id}`));
}

export function createStrategy(req: PatchStrategyRequest = {}): Promise<Strategy> {
  return unwrap(api.post<ApiResponse<Strategy>>("/strategies", req));
}

export function patchStrategy(id: string, req: PatchStrategyRequest): Promise<Strategy> {
  return unwrap(api.patch<ApiResponse<Strategy>>(`/strategies/${id}`, req));
}

export function deleteStrategy(id: string): Promise<{ ok: true }> {
  return unwrap(api.delete<ApiResponse<{ ok: true }>>(`/strategies/${id}`));
}
