/* ── 市场宏观类型 ── */

export type MarketDataStatus = "success" | "partial" | "empty" | "stale";

export interface MarketLimitation {
  code: string;
  message: string;
  index_code: string | null;
}

export type MarketSourceStatus =
  | "success_data"
  | "success_empty"
  | "failed"
  | "unsupported"
  | "stale"
  | "conflicted";

export interface MarketSourceDiagnostic {
  index_code: string;
  source_id: string;
  upstream_id: string;
  status: MarketSourceStatus;
  latency_ms: number;
  as_of: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface MarketMeta {
  status: MarketDataStatus;
  cached: boolean;
  latency_ms: number;
  missing_codes: string[];
  failed_sources: string[];
  limitations: MarketLimitation[];
  source_diagnostics: MarketSourceDiagnostic[];
  sort_requested: string | null;
  sort_applied: string | null;
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
  as_of: string;
  source_count: number;
  display_source: string | null;
  cached: boolean;
}

export interface SectorItem {
  category: "industry" | "concept";
  as_of: string | null;
  source: "eastmoney";
  snapshot_may_be_delayed: boolean;
  id: string;
  name: string;
  change_pct: number;
  fund_flow: number | null;
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

export interface ChainEvidence {
  schema_version: 1;
  sector_code: string;
  sector_name: string;
  scope: string;
  sources: { id: string; title: string; publisher: string; url: string;
    published_on: string; checked_on: string; locator: string }[];
  nodes: { id: string; label: string; kind: "industry_activity" | "company";
    stage: string; source_ids: string[]; stock_code: string | null }[];
  edges: { source_node: string; target_node: string;
    relation: "industry_sequence" | "supplies"; source_ids: string[]; description: string }[];
}

export interface SectorDetail {
  id: string;
  name: string;
  change_pct: number | null;
  fund_flow: number | null;
  heat: "high" | "medium" | "low";
  chain_map: ChainStage[];
  chain_evidence?: ChainEvidence | null;
  ai_analysis: string;
  stocks: SectorStock[];
}

export interface SectorStock {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  fund_flow: number | null;
  ai_rating: string;
}

/* ── 热点快讯 ── */

export interface HotNewsItem {
  title: string;
  date: string | null;
  source: string;
  url: string;
}
