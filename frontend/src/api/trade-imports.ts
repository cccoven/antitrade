import { api, unwrapResponse } from "./client";

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export interface TradeImportRow {
  id: string;
  row_number: number;
  record_kind: "trade" | "fill";
  status: "valid" | "warning" | "invalid" | "duplicate" | "committed";
  raw_data: Record<string, unknown>;
  normalized_data: Record<string, unknown>;
  issues: Array<{ code: string; severity: "warning" | "error" }>;
  trade_id: string | null;
}

export interface TradeImportDraft {
  id: string;
  asset_id: string;
  source_kind: "csv" | "json" | "xlsx" | "image";
  source_name: string;
  status: "preparing" | "needs_review" | "ready" | "committing" | "committed" | "failed" | "cancelled";
  mapping: Record<string, string>;
  summary: {
    total: number;
    valid: number;
    warning: number;
    invalid: number;
    duplicate: number;
    committed: number;
    created_trades?: number;
  };
  rows: TradeImportRow[];
  error_code: string | null;
}

export async function prepareTradeImport(file: File): Promise<TradeImportDraft> {
  const form = new FormData();
  form.append("file", file);
  return unwrapResponse(
    api.post<ApiResponse<TradeImportDraft>>("/trade-imports", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  );
}

export async function reviseTradeImport(
  id: string,
  mapping: Record<string, string>,
): Promise<TradeImportDraft> {
  return unwrapResponse(
    api.patch<ApiResponse<TradeImportDraft>>(`/trade-imports/${id}`, { mapping }),
  );
}

export async function commitTradeImport(id: string): Promise<TradeImportDraft> {
  return unwrapResponse(
    api.post<ApiResponse<TradeImportDraft>>(`/trade-imports/${id}/commit`),
  );
}

export async function cancelTradeImport(id: string): Promise<TradeImportDraft> {
  return unwrapResponse(
    api.post<ApiResponse<TradeImportDraft>>(`/trade-imports/${id}/cancel`),
  );
}
