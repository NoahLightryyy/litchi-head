/* ── 辩论类型 ── */

export interface DebateRequest {
  stock_code: string;
  question: string;
  enable_risk?: boolean;
  enable_trader?: boolean;
  enable_reflection?: boolean;
}

export interface DebateStatus {
  session_id: string;
  status: "running" | "completed" | "failed";
  progress?: number;
  current_stage?: string;
}

export interface AgentAnalysis {
  agent_name: string;
  skill_id: string;
  skill_name: string;
  rating: string;
  score: number;
  summary: string;
  analysis: string;
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

export interface DebateResult {
  session_id: string;
  stock_code: string;
  stock_name: string;
  question: string;
  vote_summary: VoteSummary;
  analyses: AgentAnalysis[];
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
