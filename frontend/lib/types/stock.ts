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
  fetched_at: string | null;
}

export interface KLineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
  fetched_at: string | null;
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
  gross_margin: number | null;
  net_profit_margin: number;
  revenue_growth: number;
  net_profit_growth: number;
  debt_ratio: number;
  current_ratio: number;
  quick_ratio: number;
  inventory_turnover: number;
  asset_turnover: number;
  total_assets: number;
  operating_revenue: number | null;
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

export type IntradayVerificationStatus =
  | "multi_source_verified"
  | "single_source"
  | "source_conflict"
  | "unavailable";

export type IntradayBarState = "final" | "provisional";

export type EvidenceSourceStatus =
  | "success_data"
  | "success_empty"
  | "failed"
  | "unsupported"
  | "stale"
  | "conflicted";

export type EvidenceCapability =
  | "realtime_quote"
  | "intraday"
  | "kline"
  | "cumulative_qfq_factor"
  | "corporate_action_factor"
  | "news"
  | "industry"
  | "announcement"
  | "financials"
  | "capital_flow"
  | "market_sentiment";

export interface EvidenceAssessment {
  capability: EvidenceCapability;
  complete: boolean;
  successful_upstream_ids: string[];
  successful_source_ids: string[];
  failed_source_ids: string[];
  discovery_only_source_ids: string[];
  unusable_source_ids: string[];
  missing_required_upstream_ids: string[];
  missing_independent_upstreams: number;
}

export interface IntradayPricePoint {
  code: string;
  timestamp: string;
  close: number;
  cumulative_volume: number;
  cumulative_amount: number;
  state: IntradayBarState;
}

export interface IntradayBar {
  code: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  state: IntradayBarState;
}

export interface IntradaySourceDiagnostic {
  source_id: string;
  source_name: string;
  upstream_id: string;
  status: EvidenceSourceStatus;
  fetched_at: string;
  error_code: string | null;
  error_message: string | null;
  checkpoint_count: number;
  latest_timestamp: string | null;
}

export interface IntradayBattlefieldSnapshot {
  code: string;
  evidence_level: "L1";
  as_of: string;
  current_price: number;
  current_bar_state: IntradayBarState;
  session_vwap: number | null;
  vwap_deviation_pct: number | null;
  vwap_position: "above" | "at" | "below" | "unavailable";
  opening_range_high: number | null;
  opening_range_low: number | null;
  cumulative_volume: number;
  relative_volume: number | null;
  relative_volume_sample_days: number | null;
  attribution_supported: false;
  limitations: string[];
}

export interface IntradayBattlefield {
  symbol: string;
  complete: boolean;
  usable: boolean;
  verification_status: IntradayVerificationStatus;
  canonical_source_id: string | null;
  available_source_ids: string[];
  failed_source_ids: string[];
  as_of: string | null;
  collected_at: string;
  assessment: EvidenceAssessment;
  source_diagnostics: IntradaySourceDiagnostic[];
  bars: IntradayBar[];
  price_points: IntradayPricePoint[];
  snapshot: IntradayBattlefieldSnapshot | null;
}
