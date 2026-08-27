/* ── 市场宏观类型 ── */

export type MarketDataStatus = "success" | "partial" | "empty" | "stale";

export interface MarketLimitation {
  code: string;
  message: string;
}

export interface MarketMeta {
  status: MarketDataStatus;
  cached: boolean;
  latency_ms: number;
  missing_codes: string[];
  failed_sources: string[];
  limitations: MarketLimitation[];
}

export interface MarketEnvelope<T> {
  data: T;
  meta: MarketMeta;
}

export interface MarketIndex {
  code: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
}

export interface SectorItem {
  id: string;
  name: string;
  change_pct: number;
  fund_flow: number;
  heat: "high" | "medium" | "low";
  top_stocks: string[];
  rank: number;
}

export interface MacroBrief {
  summary: string;
  generated_at: string;
  market_style: string;
  risk_tips: string[];
  hot_topics: string[];
}

/* ── 产业链类型 ── */

export interface ChainNode {
  name: string;
  companies: string[];
  is_bottleneck: boolean;
}

export interface ChainStage {
  stage: string;
  description: string;
  nodes: ChainNode[];
}

export interface ChainAnalysis {
  summary: string;
  key_links: string[];
  risk_factors: string[];
}

export interface SectorDetail {
  id: string;
  name: string;
  change_pct: number;
  fund_flow: number;
  heat: "high" | "medium" | "low";
  chain_map: ChainStage[];
  ai_analysis: string;
  stocks: SectorStock[];
}

export interface SectorStock {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  fund_flow: number;
  ai_rating: string;
}

/* ── 热点快讯 ── */

export interface HotNewsItem {
  title: string;
  date: string | null;
  source: string;
  url: string;
}
