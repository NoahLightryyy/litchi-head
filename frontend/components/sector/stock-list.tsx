"use client";

import type { SectorStock } from "@/lib/types/market";

interface StockListProps {
  stocks: SectorStock[];
  loading?: boolean;
}

/** 板块个股列表（可点击跳转到个股决策页） */
export function StockList({ stocks, loading }: StockListProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-bg-tertiary/50 border-b border-bg-tertiary animate-pulse" />
        ))}
      </div>
    );
  }

  const ratingColors: Record<string, string> = {
    "A+": "bg-accent-green/10 text-accent-green",
    "A": "bg-accent-blue/10 text-accent-blue",
    "B+": "bg-accent-gold/10 text-accent-gold",
    "B": "bg-bg-tertiary text-text-muted",
  };

  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-bg-tertiary text-text-muted text-xs uppercase tracking-wider">
            <th className="text-left px-3 py-2 font-medium">名称</th>
            <th className="text-right px-3 py-2 font-medium">涨跌</th>
            <th className="text-right px-3 py-2 font-medium">资金(亿)</th>
            <th className="text-right px-3 py-2 font-medium">AI评级</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((s) => (
            <tr
              key={s.code}
              className="border-b border-bg-tertiary last:border-0 hover:bg-bg-tertiary/50 cursor-pointer transition-colors"
              onClick={() => (window.location.href = `/stock/${s.code}`)}
            >
              <td className="px-3 py-2.5">
                <div className="flex flex-col">
                  <span className="text-text-primary font-medium">{s.name}</span>
                  <span className="text-xs text-text-muted">{s.code}</span>
                </div>
              </td>
              <td className={`px-3 py-2.5 text-right font-number ${s.change_pct >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(2)}%
              </td>
              <td className={`px-3 py-2.5 text-right font-number ${s.fund_flow >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {s.fund_flow >= 0 ? "+" : ""}{s.fund_flow.toFixed(1)}
              </td>
              <td className="px-3 py-2.5 text-right">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${ratingColors[s.ai_rating] || "bg-bg-tertiary text-text-muted"}`}>
                  {s.ai_rating}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
