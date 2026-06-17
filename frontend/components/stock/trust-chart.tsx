"use client";

import type { TrustReport } from "@/lib/types/debate";

interface TrustChartProps {
  reports: TrustReport[];
  loading?: boolean;
}

/** 信任度看板：大师历史准确率 + 校准 */
export function TrustChart({ reports, loading }: TrustChartProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 rounded-md bg-bg-tertiary" />
        ))}
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-3xl mb-3">📊</div>
        <p className="text-sm text-text-muted">暂无信任度数据（需要至少 5 次辩论记录）</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {reports.map((r) => (
        <div key={r.agent_name} className="p-4 rounded-md border border-bg-tertiary bg-bg-primary/50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-text-primary">{r.agent_name}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              r.is_reliable ? "bg-accent-green/10 text-accent-green" : "bg-accent-gold/10 text-accent-gold"
            }`}>
              {r.is_reliable ? "可靠" : "待观察"}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <span className="text-text-muted">胜率</span>
              <div className="font-number text-text-primary">{(r.win_rate * 100).toFixed(0)}%</div>
            </div>
            <div>
              <span className="text-text-muted">Brier</span>
              <div className="font-number text-text-primary">{r.brier_score.toFixed(3)}</div>
            </div>
            <div>
              <span className="text-text-muted">趋势</span>
              <div className={`font-number ${
                r.trend_direction === "improving" ? "text-accent-green" :
                r.trend_direction === "declining" ? "text-accent-red" : "text-text-primary"
              }`}>
                {r.trend_direction === "improving" ? "↑ 提升" :
                 r.trend_direction === "declining" ? "↓ 下降" : "→ 稳定"}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
