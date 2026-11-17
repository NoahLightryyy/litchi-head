/* ── 辩论类型 ── */
export type InstrumentType = "stock" | "etf";

export interface DebateRequest {
  stock_code: string;
  instrument_type?: InstrumentType;
  question: string;
  enable_risk?: boolean;
  enable_trader?: boolean;
  enable_reflection?: boolean;
}

export interface DebateStatus {
  session_id?: string | null;
  stock_code?: string | null;
  instrument_type?: InstrumentType | null;
  status: "queued" | "running" | "completed" | "failed" | "not_found" | "unknown";
  progress?: number;
  current_stage?: string;
}

export interface AgentAnalysis {
  horizons?: import("../research-horizon").HorizonOpinion[];
  research_generated_at?: string | null;
  agent_name: string;
  skill_id: string;
  skill_name: string;
  rating: string;
  score: number;
  summary: string;
  analysis: string;
  key_evidence?: string[];
  risk_warning?: string | null;
  error?: string | null;
  confidence: number;
  direction: string;
  success: boolean;
  latency_ms: number;
}

/* ── DP-003: 偏斜公示 ───────────────────────────── */
export interface BiasReport {
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  total_count: number;
  bullish_ratio: number;
  bearish_ratio: number;
  neutral_ratio: number;
  overall_bias: number;
  consensus_strength: number;
  consensus_type: 'Bullish' | 'Bearish' | 'Neutral' | 'Divided';
  historical_avg_bias: number;
}

export interface VoteSummary {
  consensus: string;
  weighted_score: number;
  confidence: number;
  direction_distribution: Record<string, number>;
  rating_distribution: Record<string, number>;
  trust_weight_factors: Record<string, number>;
  review_score: number;
  review_rating: string;
  bias_report: BiasReport;
}

export interface EvidenceLimitation {
  status: "limited";
  research_note?: string | null;
  error_codes?: string[];
  capability: string;
  missing_upstream_ids: string[];
  missing_independent_upstreams: number;
  source_statuses: Record<string, string>;
  collected_at: string;
}

export interface DebateResult {
  session_id: string;
  stock_code: string;
  instrument_type?: InstrumentType;
  stock_name: string;
  question: string;
  vote_summary: VoteSummary;
  analyses: AgentAnalysis[];
  evidence_limitations?: EvidenceLimitation[];
  review_report?: { overall_quality: number } | null;
  total_latency_ms: number;
  created_at: string;
}

export interface TrustReport {
  agent_name: string;
  win_rate: number;
  brier_score: number;
  confidence_bias: number;
  trend_direction: "improving" | "declining" | "stable";
  total_predictions: number;
  is_reliable: boolean;
  summary: string;
}

export interface DebateHistoryItem {
  session_id: string;
  stock_code: string;
  instrument_type?: InstrumentType;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  error: string | null;
}
