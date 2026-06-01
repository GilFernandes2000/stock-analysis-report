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
  report_type: string;
  title: string;
  created_at: string;
}

export interface ReportDetail {
  id: number;
  report_type: string;
  title: string;
  content_json: {
    report_type: string;
    label: string;
    description: string;
    stale: boolean;
    stocks: Array<Record<string, unknown>>;
    generated_at: string;
  };
  content_markdown: string;
  created_at: string;
}

export interface Holding {
  id: number;
  ticker: string;
  shares: number;
  avg_cost: number;
  notes?: string | null;
  added_at: string;
}

export interface HoldingInsight {
  ticker: string;
  shares: number;
  avg_cost: number;
  current_price?: number | null;
  market_value?: number | null;
  cost_basis: number;
  unrealized_pnl?: number | null;
  unrealized_pnl_pct?: number | null;
  sector?: string | null;
  trend_label: string;
  sentiment_label: string;
}

export interface SectorAllocation {
  sector: string;
  weight_pct: number;
  value: number;
}

export interface PortfolioInsights {
  display_currency?: string;
  holdings: HoldingInsight[];
  total_cost_basis: number;
  total_market_value?: number | null;
  total_unrealized_pnl?: number | null;
  total_unrealized_pnl_pct?: number | null;
  sector_allocation: SectorAllocation[];
  risk_flags: string[];
  stale: boolean;
}
