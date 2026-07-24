export interface TrendAnalysis {
  score: number;
  label: string;
  signals: string[];
}

export interface NewsItem {
  title: string;
  url?: string | null;
  date?: string | null;
  sentiment?: string | null;
  compound_score?: number | null;
}

export interface SentimentSummary {
  label: string;
  average_compound: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  headlines: NewsItem[];
}

export interface AnalystTarget {
  analyst?: string | null;
  price_target?: number | null;
  native_price_target?: number | null;
  date?: string | null;
}

export interface InsiderTrade {
  insider?: string | null;
  relationship?: string | null;
  transaction?: string | null;
  shares?: string | null;
  value?: string | null;
  date?: string | null;
}

export interface InsiderSignal {
  label: "Bullish" | "Neutral" | "Bearish" | "No activity";
  score: number;
  window_days: number;
  buy_count: number;
  sell_count: number;
  buyers: number;
  sellers: number;
  buy_value: number;
  sell_value: number;
  net_value: number;
  signals: string[];
  summary: string;
}

export interface HoldingInsider {
  ticker: string;
  name?: string | null;
  signal: InsiderSignal;
}

export interface PortfolioInsiderResponse {
  portfolio_id: number;
  as_of: string;
  holdings: HoldingInsider[];
  advice: string[];
  no_data_tickers: string[];
}

export interface StockAnalysis {
  ticker: string;
  company?: string | null;
  sector?: string | null;
  industry?: string | null;
  country?: string | null;
  exchange?: string | null;
  currency?: string | null;
  native_currency?: string | null;
  native_price?: number | null;
  display_currency?: string;
  display_price?: number | null;
  currency_note?: string | null;
  data_source?: string;
  price?: number | null;
  change?: string | null;
  market_cap?: string | null;
  pe?: string | null;
  eps?: string | null;
  dividend?: string | null;
  beta?: string | null;
  rsi?: number | null;
  sma20?: number | null;
  sma50?: number | null;
  sma200?: number | null;
  inst_own?: string | null;
  insider_own?: string | null;
  short_float?: string | null;
  perf_week?: string | null;
  perf_month?: string | null;
  perf_quarter?: string | null;
  perf_ytd?: string | null;
  high_52w?: string | null;
  low_52w?: string | null;
  chart_url?: string | null;
  trend: TrendAnalysis;
  sentiment: SentimentSummary;
  analyst_targets: AnalystTarget[];
  analyst_upside_pct?: number | null;
  insider_trades: InsiderTrade[];
  insider_signal?: InsiderSignal | null;
  stale: boolean;
  disclaimer: string;
}

export interface ScreenerStockRow {
  ticker: string;
  company?: string | null;
  sector?: string | null;
  price?: string | null;
  change?: string | null;
  market_cap?: string | null;
  extra: Record<string, string>;
}

export interface ScreenerResponse {
  preset: string;
  label: string;
  description: string;
  count: number;
  stocks: ScreenerStockRow[];
  stale: boolean;
}

export interface ReportSummary {
  id: number;
  kind: string;
  report_type: string;
  title: string;
  created_at: string;
}

export interface MarketReportContent {
  report_type: string;
  label: string;
  description: string;
  stale: boolean;
  stocks: Array<Record<string, unknown>>;
  generated_at: string;
}

export interface ReportDetail {
  id: number;
  kind: string;
  report_type: string;
  title: string;
  content_json: MarketReportContent | TearsheetContent;
  content_markdown: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  username: string;
  display_name: string;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

// ---------------------------------------------------------------------------
// Portfolios & transactions
// ---------------------------------------------------------------------------

export type TransactionType =
  | "buy"
  | "sell"
  | "dividend"
  | "deposit"
  | "withdrawal"
  | "fee"
  | "interest"
  | "tax"
  | "other";

export interface Portfolio {
  id: number;
  name: string;
  broker: string;
  base_currency: string;
  benchmark: string;
  created_at: string;
  transaction_count: number;
}

export interface PortfolioSummary extends Portfolio {
  market_value?: number | null;
  total_return?: number | null;
  total_return_pct?: number | null;
  day_change_pct?: number | null;
  position_count: number;
}

export interface Transaction {
  id: number;
  portfolio_id: number;
  type: TransactionType;
  date: string;
  ticker?: string | null;
  isin?: string | null;
  name?: string | null;
  shares?: number | null;
  price?: number | null;
  currency?: string | null;
  amount: number;
  fees: number;
  fx_rate?: number | null;
  note?: string | null;
  external_id?: string | null;
  created_at: string;
}

export interface TransactionCreate {
  type: TransactionType;
  date: string;
  ticker?: string | null;
  isin?: string | null;
  name?: string | null;
  shares?: number | null;
  price?: number | null;
  currency?: string | null;
  amount: number;
  fees?: number;
  note?: string | null;
}

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

export interface ImportRow {
  type: TransactionType;
  date: string;
  ticker?: string | null;
  isin?: string | null;
  name?: string | null;
  shares?: number | null;
  price?: number | null;
  currency?: string | null;
  amount: number;
  fees: number;
  fx_rate?: number | null;
  note?: string | null;
  external_id?: string | null;
  duplicate: boolean;
  ticker_resolved: boolean;
}

export interface ImportPreview {
  broker: string;
  file_kind: string;
  rows: ImportRow[];
  total_rows: number;
  duplicate_count: number;
  unresolved_isins: string[];
  warnings: string[];
}

export interface ImportCommitResult {
  imported: number;
  skipped: number;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface Position {
  ticker: string;
  name?: string | null;
  isin?: string | null;
  shares: number;
  avg_cost: number;
  cost_basis: number;
  current_price?: number | null;
  native_price?: number | null;
  native_currency?: string | null;
  market_value?: number | null;
  weight_pct?: number | null;
  unrealized_pnl?: number | null;
  unrealized_pnl_pct?: number | null;
  realized_pnl: number;
  dividends: number;
  fees: number;
  day_change_pct?: number | null;
  sector?: string | null;
  country?: string | null;
  trend_label?: string | null;
  first_bought?: string | null;
}

export interface ClosedPosition {
  ticker: string;
  name?: string | null;
  realized_pnl: number;
  dividends: number;
  fees: number;
}

export interface AllocationSlice {
  label: string;
  value: number;
  weight_pct: number;
}

export interface PerformancePoint {
  date: string;
  value: number;
  cost_basis: number;
  benchmark?: number | null;
  twr_index?: number | null;
}

export interface RiskMetrics {
  volatility_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  beta?: number | null;
  twr_pct?: number | null;
  benchmark_return_pct?: number | null;
  best_day_pct?: number | null;
  worst_day_pct?: number | null;
}

export interface ContributorEntry {
  ticker: string;
  name?: string | null;
  total_pnl: number;
  return_pct?: number | null;
}

export interface CashFlowSummary {
  deposits: number;
  withdrawals: number;
  dividends: number;
  interest: number;
  fees: number;
  taxes: number;
  invested: number;
  cash_balance: number;
}

export interface PortfolioAnalytics {
  portfolio_id: number;
  name: string;
  base_currency: string;
  benchmark: string;
  as_of: string;
  market_value: number;
  cost_basis: number;
  cash_balance: number;
  total_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct?: number | null;
  realized_pnl: number;
  dividends_received: number;
  fees_paid: number;
  total_return: number;
  total_return_pct?: number | null;
  day_change?: number | null;
  day_change_pct?: number | null;
  positions: Position[];
  closed_positions: ClosedPosition[];
  sector_allocation: AllocationSlice[];
  currency_allocation: AllocationSlice[];
  country_allocation: AllocationSlice[];
  performance: PerformancePoint[];
  risk: RiskMetrics;
  top_contributors: ContributorEntry[];
  top_detractors: ContributorEntry[];
  cash_flows: CashFlowSummary;
  risk_flags: string[];
  stale: boolean;
}

// ---------------------------------------------------------------------------
// Tearsheet report
// ---------------------------------------------------------------------------

export interface HoldingCommentary {
  ticker: string;
  name?: string | null;
  weight_pct?: number | null;
  text: string;
}

export interface TearsheetCommentary {
  executive_summary: string;
  performance: string;
  risk: string;
  allocation: string;
  holdings: HoldingCommentary[];
  outlook: string[];
}

export interface HoldingResearch {
  ticker: string;
  trend_label?: string;
  trend_score?: number;
  sentiment_label?: string;
  rsi?: number | null;
  analyst_upside_pct?: number | null;
  recommendation?: string | null;
  pe?: string | null;
  dividend?: string | null;
  error?: string;
}

export interface TearsheetSection {
  portfolio: PortfolioAnalytics;
  holdings_analysis: HoldingResearch[];
  commentary: TearsheetCommentary;
}

export interface TearsheetContent {
  kind: "portfolio";
  title: string;
  generated_at: string;
  portfolio_count: number;
  combined?: {
    portfolio_names: string[];
    market_value: number;
    total_return: number;
    dividends_received: number;
    fees_paid: number;
    mixed_currencies: boolean;
    base_currency: string;
  } | null;
  sections: TearsheetSection[];
}
