import type {
  Holding,
  PortfolioInsights,
  ReportDetail,
  ReportSummary,
  ScreenerResponse,
  StockAnalysis,
} from "../types";
import { currencyQueryParam } from "../utils/currency";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function withCurrency(url: string): string {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}${currencyQueryParam()}`;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  supportedCurrencies: () =>
    request<{ default: string; supported: string[] }>("/api/currency/supported"),

  getStock: (ticker: string) =>
    request<StockAnalysis>(withCurrency(`/api/stocks/${encodeURIComponent(ticker)}`)),

  listScreenerPresets: () =>
    request<Record<string, { label: string; description: string }>>(
      "/api/screener/presets"
    ),

  getScreener: (preset: string) =>
    request<ScreenerResponse>(`/api/screener/${encodeURIComponent(preset)}`),

  listReports: (reportType?: string) => {
    const params = reportType ? `?report_type=${reportType}` : "";
    return request<ReportSummary[]>(`/api/reports${params}`);
  },

  latestReports: () => request<ReportDetail[]>("/api/reports/latest"),

  getReport: (id: number) => request<ReportDetail>(`/api/reports/${id}`),

  generateReports: (reportTypes?: string[]) =>
    request<ReportDetail[]>("/api/reports/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_types: reportTypes ?? null }),
    }),

  listHoldings: () => request<Holding[]>("/api/portfolio"),

  createHolding: (data: {
    ticker: string;
    shares: number;
    avg_cost: number;
    notes?: string;
  }) =>
    request<Holding>("/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  updateHolding: (
    id: number,
    data: { shares?: number; avg_cost?: number; notes?: string }
  ) =>
    request<Holding>(`/api/portfolio/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  deleteHolding: (id: number) =>
    request<void>(`/api/portfolio/${id}`, { method: "DELETE" }),

  portfolioInsights: () =>
    request<PortfolioInsights>(withCurrency("/api/portfolio/insights")),
};
