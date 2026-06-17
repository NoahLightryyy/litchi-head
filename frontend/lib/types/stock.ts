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
