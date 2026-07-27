"use client";

import type { TrustReport } from "@/lib/types/debate";

interface TrustChartProps {
  reports: TrustReport[];
  loading?: boolean;
}

/** 信任度看板：大师历史准确率 + 校准 + 置信度偏差 */
export function TrustChart({ reports, loading }: TrustChartProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 rounded-md bg-bg-tertiary" />
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
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-text-muted">胜率</span>
              <div className="font-number text-text-primary">{(r.win_rate * 100).toFixed(0)}%</div>
            </div>
            <div>
              <span className="text-text-muted">Brier 校准</span>
              <div className="font-number text-text-primary">{r.brier_score.toFixed(3)}</div>
            </div>
            <div>
              <span className="text-text-muted">置信度偏差</span>
              <div className={`font-number ${
                Math.abs(r.confidence_bias) < 0.1 ? "text-accent-green" :
                Math.abs(r.confidence_bias) < 0.2 ? "text-accent-gold" : "text-accent-red"
              }`}>
                {r.confidence_bias > 0 ? "过度自信" : r.confidence_bias < 0 ? "保守" : "校准良好"}
                <span className="text-text-muted ml-1">({(r.confidence_bias * 100).toFixed(0)}%)</span>
              </div>
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
          {/* 样本数 */}
          <div className="mt-2 text-[10px] text-text-muted">
            样本: {r.total_predictions} 次 · {r.is_reliable ? "已参与权重调整" : "权重待激活"}
          </div>
        </div>
      ))}
    </div>
  );
}
