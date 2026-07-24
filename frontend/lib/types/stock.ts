/* ── 个股类型 ── */

export interface StockQuote {
  code: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  open: number;
  high: number;
  low: number;
  prev_close: number;
  volume: number;
  turnover_rate: number;
  fund_flow: number;
  market_cap: number;
  amount: number;
}

export interface KLineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
}

export interface NewsItem {
  code: string;
  title: string;
  date: string;
  content: string;
  source: string;
  url: string;
}

export interface CapitalFlow {
  date: string;
  main_net_inflow: number;
  retail_net_inflow: number;
  institutional_net_inflow: number;
}

export interface StockSearchResult {
  code: string;
  name: string;
  type: "stock" | "sector";
  market?: string;
}

/* ── 技术指标类型 ── */

export interface MaResult {
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
}

export interface MacdResult {
  value: number | null;
  signal: number | null;
  histogram: number | null;
}

export interface BollingerResult {
  upper: number | null;
  middle: number | null;
  lower: number | null;
}

export interface TechnicalIndicators {
  ma: MaResult;
  rsi: number | null;
  macd: MacdResult;
  bollinger: BollingerResult;
}

/* ── 财务指标类型 ── */

export interface FinancialMetrics {
  stock_code: string;
  report_date: string;
  eps: number;
  book_value_per_share: number;
  operating_cf_per_share: number;
  roe: number;
  roa: number;
  gross_margin: number;
  net_profit_margin: number;
  revenue_growth: number;
  net_profit_growth: number;
  debt_ratio: number;
  current_ratio: number;
  quick_ratio: number;
  inventory_turnover: number;
  asset_turnover: number;
  total_assets: number;
  operating_revenue: number;
}

export interface ValuationMetrics {
  stock_code: string;
  report_date: string;
  pe: number;
  pb: number;
  ps: number;
  market_cap: number;
}

/* ── 动态指标类型（PD 行业感知） ── */

export interface IndicatorDef {
  id: string;
  name: string;
  description: string;
  unit: string;
  normal_range_hint: string;
  higher_is_better: boolean;
  priority: number;
}

export interface DynamicIndicators {
  industry: string;
  chain_position: string;
  indicator_ids: string[];
  indicators: IndicatorDef[];
}
