import type { AxiosResponse } from "axios";
import { api, unwrapResponse } from "./client";

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export type AutomationTaskType =
  | "risk_guardian"
  | "news_impact"
  | "market_watch"
  | "condition_monitor"
  | "session_report"
  | "plan_guardian";
export type AutomationTaskStatus = "active" | "paused" | "disabled";
export type FindingSeverity = "info" | "warning" | "critical";
export type FindingStatus = "open" | "acknowledged" | "resolved" | "suppressed";

export interface AutomationTask {
  id: string;
  name: string;
  task_type: AutomationTaskType;
  status: AutomationTaskStatus;
  schedule_kind: "interval" | "daily";
  schedule_config: Record<string, unknown>;
  timezone: string;
  scope: {
    symbols?: string[];
    interval?: "5min" | "15min" | "1h" | "4h" | "1day";
    condition_kind?: "percent_change" | "price_above" | "price_below";
    threshold?: number;
    proximity_percent?: number;
    analysis_instruction?: string;
  };
  notification_config: {
    enabled?: boolean;
    min_severity?: FindingSeverity;
    channel_id?: string | null;
    locale?: "zh" | "en";
  };
  next_run_at: string;
  last_run_at: string | null;
  consecutive_failures: number;
  created_at: string;
  updated_at: string;
}

export interface AutomationRun {
  id: string;
  task_id: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed" | "skipped";
  scheduled_for: string;
  started_at: string | null;
  finished_at: string | null;
  input_as_of: string | null;
  summary: string;
  error_code: string | null;
}

export interface AgentFinding {
  id: string;
  task_id: string;
  finding_type: "risk" | "news" | "data_quality" | "market" | "plan";
  severity: FindingSeverity;
  status: FindingStatus;
  subject_type: string | null;
  subject_id: string | null;
  title: string;
  body: string;
  evidence: Array<Record<string, unknown>>;
  payload: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  expires_at: string | null;
}

export interface AgentReport {
  id: string;
  task_id: string;
  task_name: string;
  task_type: "market_watch" | "session_report";
  status: "succeeded" | "partial";
  summary: string;
  summary_en: string;
  output: {
    evidence?: Array<Record<string, unknown>>;
    metrics?: Record<string, unknown>;
    analysis?: {
      instruction?: string;
      status?: "applied" | "fallback";
      model?: string;
    };
  };
  as_of: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface TaskDraft {
  name: string;
  task_type: AutomationTaskType;
  schedule_kind: "interval" | "daily";
  schedule_config: Record<string, unknown>;
  timezone: string;
  scope: AutomationTask["scope"];
  notification_config: {
    enabled: boolean;
    min_severity: FindingSeverity;
    channel_id: string | null;
    locale: "zh" | "en";
  };
}

function unwrap<T>(promise: Promise<AxiosResponse<ApiResponse<T>>>) {
  return unwrapResponse(promise);
}

export function listAutomationTasks(): Promise<AutomationTask[]> {
  return unwrap(api.get<ApiResponse<AutomationTask[]>>("/automations/tasks"));
}

export function createAutomationTask(draft: TaskDraft): Promise<AutomationTask> {
  return unwrap(api.post<ApiResponse<AutomationTask>>("/automations/tasks", draft));
}

export function patchAutomationTask(
  id: string,
  updates: Partial<TaskDraft> & { status?: AutomationTaskStatus },
): Promise<AutomationTask> {
  return unwrap(api.patch<ApiResponse<AutomationTask>>(`/automations/tasks/${id}`, updates));
}

export function deleteAutomationTask(id: string): Promise<null> {
  return unwrap(api.delete<ApiResponse<null>>(`/automations/tasks/${id}`));
}

export function runAutomationTask(id: string): Promise<AutomationRun> {
  return unwrap(api.post<ApiResponse<AutomationRun>>(`/automations/tasks/${id}/run`));
}

export function listAutomationRuns(id: string): Promise<AutomationRun[]> {
  return unwrap(api.get<ApiResponse<AutomationRun[]>>(`/automations/tasks/${id}/runs`));
}

export function listAgentFindings(params?: {
  status?: FindingStatus;
  severity?: FindingSeverity;
  finding_type?: string;
  limit?: number;
}): Promise<AgentFinding[]> {
  return unwrap(api.get<ApiResponse<AgentFinding[]>>("/automations/findings", { params }));
}

export function listAgentReports(params?: { limit?: number }): Promise<AgentReport[]> {
  return unwrap(api.get<ApiResponse<AgentReport[]>>("/automations/reports", { params }));
}
