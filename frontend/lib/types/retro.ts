/* ── 复盘记录类型 ── */

export interface RetroRecord {
  record_id: string;
  session_id: string;
  stock_code: string;
  stock_name: string;
  created_at: string;
  debate_latency_ms: number;
  consensus: string;
  weighted_score: number;
  confidence: number;
  direction_distribution: Record<string, number>;
  avg_score: number;
  rating_distribution: Record<string, number>;
  price_at_debate: number | null;
  user_action: string | null;
  user_action_at: string | null;
  actual_return_pct: number | null;
  actual_price: number | null;
  outcome: "correct" | "wrong" | "pending";
  notes: string;
}

export interface RetroSummary {
  total_records: number;
  today_records: number;
  closed_records: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  avg_confidence: number;
  avg_score: number;
  last_record_at: string | null;
}

export interface RefreshResult {
  total_pending: number;
  updated: number;
  errors: number;
}
