import type {
  AuthResponse,
  Favorite,
  ImportCommitResult,
  ImportPreview,
  ImportRow,
  Portfolio,
  PortfolioAnalytics,
  PortfolioInsiderResponse,
  PortfolioSummary,
  PresetMeta,
  QuotesResponse,
  ReportDetail,
  ReportSummary,
  ScreenerResponse,
  StockAnalysis,
  Transaction,
  TransactionCreate,
  User,
} from "../types";
import { currencyQueryParam } from "../utils/currency";

const TOKEN_KEY = "authToken";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) {
      setToken(null);
      window.dispatchEvent(new CustomEvent("auth:expired"));
    }
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = await res.text().catch(() => "");
    }
    throw new ApiError(res.status, detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function json(body: unknown): RequestInit {
  return {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function withCurrency(url: string): string {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}${currencyQueryParam()}`;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  // --- auth ---
  register: (username: string, displayName: string, password: string) =>
    request<AuthResponse>("/api/auth/register", {
      method: "POST",
      ...json({ username, display_name: displayName, password }),
    }),
  login: (username: string, password: string) =>
    request<AuthResponse>("/api/auth/login", {
      method: "POST",
      ...json({ username, password }),
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  me: () => request<User>("/api/auth/me"),

  // --- research ---
  supportedCurrencies: () =>
    request<{ default: string; supported: string[] }>("/api/currency/supported"),
  getStock: (ticker: string) =>
    request<StockAnalysis>(withCurrency(`/api/stocks/${encodeURIComponent(ticker)}`)),
  listScreenerPresets: () =>
    request<Record<string, PresetMeta>>("/api/screener/presets"),
  listMovers: () => request<Record<string, PresetMeta>>("/api/screener/movers"),
  getScreener: (preset: string) =>
    request<ScreenerResponse>(`/api/screener/${encodeURIComponent(preset)}`),

  // --- favorites ---
  listFavorites: () => request<Favorite[]>("/api/favorites"),
  addFavorite: (ticker: string) =>
    request<Favorite>("/api/favorites", { method: "POST", ...json({ ticker }) }),
  removeFavorite: (ticker: string) =>
    request<void>(`/api/favorites/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    }),
  favoriteQuotes: () =>
    request<QuotesResponse>(withCurrency("/api/favorites/quotes")),

  // --- portfolios ---
  listPortfolios: (quotes = false) =>
    request<PortfolioSummary[]>(`/api/portfolios?quotes=${quotes}`),
  createPortfolio: (data: {
    name: string;
    broker: string;
    base_currency: string;
    benchmark?: string;
  }) => request<Portfolio>("/api/portfolios", { method: "POST", ...json(data) }),
  updatePortfolio: (
    id: number,
    data: Partial<{ name: string; broker: string; base_currency: string; benchmark: string }>
  ) => request<Portfolio>(`/api/portfolios/${id}`, { method: "PUT", ...json(data) }),
  deletePortfolio: (id: number) =>
    request<void>(`/api/portfolios/${id}`, { method: "DELETE" }),
  portfolioAnalytics: (id: number) =>
    request<PortfolioAnalytics>(`/api/portfolios/${id}/analytics`),
  portfolioInsider: (id: number) =>
    request<PortfolioInsiderResponse>(`/api/portfolios/${id}/insider`),

  // --- transactions ---
  listTransactions: (portfolioId: number) =>
    request<Transaction[]>(`/api/portfolios/${portfolioId}/transactions`),
  addTransaction: (portfolioId: number, data: TransactionCreate) =>
    request<Transaction>(`/api/portfolios/${portfolioId}/transactions`, {
      method: "POST",
      ...json(data),
    }),
  deleteTransaction: (portfolioId: number, txnId: number) =>
    request<void>(`/api/portfolios/${portfolioId}/transactions/${txnId}`, {
      method: "DELETE",
    }),

  // --- import ---
  importPreview: (portfolioId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportPreview>(`/api/portfolios/${portfolioId}/import/preview`, {
      method: "POST",
      body: form,
    });
  },
  importCommit: (portfolioId: number, rows: ImportRow[], skipDuplicates = true) =>
    request<ImportCommitResult>(`/api/portfolios/${portfolioId}/import/commit`, {
      method: "POST",
      ...json({ rows, skip_duplicates: skipDuplicates }),
    }),

  // --- reports ---
  listReports: (kind?: string) => {
    const params = kind ? `?kind=${kind}` : "";
    return request<ReportSummary[]>(`/api/reports${params}`);
  },
  latestReports: () => request<ReportDetail[]>("/api/reports/latest"),
  getReport: (id: number) => request<ReportDetail>(`/api/reports/${id}`),
  deleteReport: (id: number) =>
    request<void>(`/api/reports/${id}`, { method: "DELETE" }),
  generateReports: (reportTypes?: string[]) =>
    request<ReportDetail[]>("/api/reports/generate", {
      method: "POST",
      ...json({ report_types: reportTypes ?? null }),
    }),
  generateTearsheet: (portfolioIds: number[]) =>
    request<ReportDetail>("/api/reports/tearsheet", {
      method: "POST",
      ...json({ portfolio_ids: portfolioIds }),
    }),
};
