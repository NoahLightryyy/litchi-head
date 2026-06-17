"use client";

import type { SectorItem } from "@/lib/types/market";
import { formatChangePct, changeColor } from "@/lib/utils";

interface SectorRankingProps {
  sectors: SectorItem[];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
}

/** 板块排行表格 */
export function SectorRanking({ sectors, loading, error, onRetry, sortBy, onSortChange }: SectorRankingProps) {
  const heatLabels = { high: "🔥", medium: "📌", low: "—" } as const;

  if (loading) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden animate-pulse">
        <div className="h-10 bg-bg-tertiary" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-bg-tertiary/50 border-t border-bg-tertiary" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-4 text-center">
        <p className="text-sm text-text-muted mb-2">板块数据加载失败</p>
        {onRetry && (
          <button onClick={onRetry} className="text-xs text-accent-blue hover:underline">重新加载</button>
        )}
      </div>
    );
  }

  if (!sectors.length) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 text-center">
        <p className="text-xs text-text-muted">暂无板块数据</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-bg-tertiary text-text-muted text-xs uppercase tracking-wider">
            <th className="text-left px-4 py-3 font-medium">排名</th>
            <th className="text-left px-4 py-3 font-medium">板块</th>
            <th
              className="text-right px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
              onClick={() => onSortChange("change_pct")}
            >
              涨跌幅 {sortBy === "change_pct" ? "↓" : ""}
            </th>
            <th
              className="text-right px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
              onClick={() => onSortChange("fund_flow")}
            >
              主力净流入(亿) {sortBy === "fund_flow" ? "↓" : ""}
            </th>
            <th className="text-right px-4 py-3 font-medium">热度</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map((s) => (
            <tr
              key={s.id}
              className="border-b border-bg-tertiary last:border-0 hover:bg-bg-tertiary/50 cursor-pointer transition-colors"
              onClick={() => (window.location.href = `/sector/${s.id}`)}
            >
              <td className="px-4 py-3 text-text-muted text-xs">{s.rank}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col">
                  <span className="text-text-primary font-medium">{s.name}</span>
                  <span className="text-xs text-text-muted">
                    {s.top_stocks.slice(0, 2).join(" · ")}
                  </span>
                </div>
              </td>
              <td className={`px-4 py-3 text-right font-number ${changeColor(s.change_pct)}`}>
                {formatChangePct(s.change_pct)}
              </td>
              <td className={`px-4 py-3 text-right font-number ${s.fund_flow >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {s.fund_flow >= 0 ? "+" : ""}{s.fund_flow.toFixed(1)}
              </td>
              <td className="px-4 py-3 text-right">{heatLabels[s.heat]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
