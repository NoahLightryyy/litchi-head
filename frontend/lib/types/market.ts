/* ── 市场宏观类型 ── */

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
