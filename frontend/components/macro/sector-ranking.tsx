"use client";

import { useState } from "react";
import type { MarketMeta, SectorItem } from "@/lib/types/market";
import { formatChangePct, changeColor } from "@/lib/utils";
import {
  DEFAULT_VISIBLE_SECTOR_COUNT,
  hiddenSectorCount,
  visibleSectorItems,
} from "@/lib/sector-ranking-view";
import { MarketDataNotice } from "./market-data-notice";

interface SectorRankingProps {
  sectors: SectorItem[];
  loading?: boolean;
  error?: boolean;
  meta?: MarketMeta;
  refreshError?: boolean;
  onRetry?: () => void;
  onSortChange: (sort: string) => void;
}

/** 板块排行表格 */
export function SectorRanking({ sectors, loading, error, meta, refreshError, onRetry, onSortChange }: SectorRankingProps) {
  const heatLabels = { high: "🔥", medium: "📌", low: "—" } as const;
  const [expanded, setExpanded] = useState(false);
  const visibleSectors = visibleSectorItems(sectors, expanded);
  const hiddenCount = hiddenSectorCount(sectors, expanded);

  const handleSortChange = (sort: string) => {
    setExpanded(false);
    onSortChange(sort);
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden" aria-live="polite">
        <div className="px-4 py-3 text-xs text-text-muted">正在获取板块排行…</div>
        <div className="animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-bg-tertiary/50 border-t border-bg-tertiary" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !sectors.length) {
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
    <>
      <MarketDataNotice meta={meta} refreshError={refreshError} />
      <div className="max-h-[32rem] overflow-auto rounded-lg border border-bg-tertiary bg-bg-secondary">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-bg-secondary">
          <tr className="border-b border-bg-tertiary text-text-muted text-xs uppercase tracking-wider">
            <th className="text-left px-4 py-3 font-medium">排名</th>
            <th className="text-left px-4 py-3 font-medium">板块</th>
            <th
              className="text-right px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
              onClick={() => handleSortChange("change_pct")}
            >
              涨跌幅 {meta?.sort_applied === "change_pct" ? "↓" : ""}
            </th>
            <th
              className="text-right px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
              onClick={() => handleSortChange("fund_flow")}
            >
              主力净流入(亿) {meta?.sort_applied === "fund_flow" ? "↓" : ""}
            </th>
            <th className="text-right px-4 py-3 font-medium">热度</th>
          </tr>
        </thead>
        <tbody>
          {visibleSectors.map((s) => (
            <tr
              key={`${s.id}-${s.rank}`}
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
              <td className={`px-4 py-3 text-right font-number ${s.fund_flow === null ? "text-text-muted" : s.fund_flow >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {s.fund_flow === null ? "—" : `${s.fund_flow >= 0 ? "+" : ""}${s.fund_flow.toFixed(1)}`}
              </td>
              <td className="px-4 py-3 text-right">{heatLabels[s.heat]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sectors.length > DEFAULT_VISIBLE_SECTOR_COUNT && (
        <div className="sticky bottom-0 border-t border-bg-tertiary bg-bg-secondary/95 px-4 py-2 text-center backdrop-blur">
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="text-xs text-accent-blue hover:underline"
          >
            {expanded
              ? `收起，仅显示前 ${DEFAULT_VISIBLE_SECTOR_COUNT} 个`
              : `展开其余 ${hiddenCount} 个板块`}
          </button>
        </div>
      )}
      </div>
    </>
  );
}
