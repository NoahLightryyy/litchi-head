"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import type { MarketMeta, SectorItem } from "@/lib/types/market";
import { formatChangePct, changeColor } from "@/lib/utils";
import {
  DEFAULT_VISIBLE_SECTOR_COUNT,
  hiddenSectorCount,
  visibleSectorItems,
  sectorChangeScale,
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
  const [visibleCount, setVisibleCount] = useState(DEFAULT_VISIBLE_SECTOR_COUNT);
  const visibleSectors = visibleSectorItems(sectors, visibleCount);
  const hiddenCount = hiddenSectorCount(sectors, visibleCount);
  const changeScale = sectorChangeScale(sectors);
  const tableContainer = useRef<HTMLDivElement>(null);

  const collapse = () => {
    setVisibleCount(DEFAULT_VISIBLE_SECTOR_COUNT);
    tableContainer.current?.scrollTo({ top: 0 });
  };

  const handleSortChange = (sort: string) => {
    collapse();
    onSortChange(sort);
  };

  if (loading && !sectors.length) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden" role="status" aria-label="板块排行加载中">
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
      <div className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-4 text-center" role="alert">
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
      <div className="flex flex-wrap items-center justify-between gap-2 py-2 text-xs text-text-muted">
        <span role="status">显示 {visibleSectors.length} / {sectors.length} 个板块</span>
        <span>涨跌幅条以 0 为中线，同一比例</span>
      </div>
      <div ref={tableContainer} className="max-h-[32rem] overflow-auto rounded-lg border border-bg-tertiary bg-bg-secondary">
      <table className="w-full min-w-[34rem] text-sm" aria-label="板块排行榜">
        <thead className="sticky top-0 z-10 bg-bg-secondary">
          <tr className="border-b border-bg-tertiary text-text-muted text-xs uppercase tracking-wider">
            <th className="text-left px-4 py-3 font-medium">排名</th>
            <th className="text-left px-4 py-3 font-medium">板块</th>
            <th
              className="text-right px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
              aria-sort={meta?.sort_applied === "change_pct" ? "descending" : "none"}
            >
              <button type="button" onClick={() => handleSortChange("change_pct")} className="focus-visible:outline-2 focus-visible:outline-accent-blue">涨跌幅 {meta?.sort_applied === "change_pct" ? "↓" : ""}</button>
            </th>
            <th
              className="text-right px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
              aria-sort={meta?.sort_applied === "fund_flow" ? "descending" : "none"}
            >
              <button type="button" onClick={() => handleSortChange("fund_flow")} className="focus-visible:outline-2 focus-visible:outline-accent-blue">主力净流入(亿) {meta?.sort_applied === "fund_flow" ? "↓" : ""}</button>
            </th>
            <th className="text-right px-4 py-3 font-medium">热度</th>
          </tr>
        </thead>
        <tbody>
          {visibleSectors.map((s) => (
            <tr
              key={`${s.id}-${s.rank}`}
              className="border-b border-bg-tertiary last:border-0 hover:bg-bg-tertiary/50 cursor-pointer transition-colors"
            >
              <td className="px-4 py-3 text-text-muted text-xs">{s.rank}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col">
                  <Link href={`/sector/${s.id}`} className="text-text-primary font-medium hover:underline focus-visible:outline-2 focus-visible:outline-accent-blue">{s.name}</Link>
                  <span className="text-xs text-text-muted">
                    {s.top_stocks.slice(0, 2).join(" · ")}
                  </span>
                </div>
              </td>
              <td className={`px-4 py-3 text-right font-number ${changeColor(s.change_pct)}`}>
                {formatChangePct(s.change_pct)}
                <div aria-hidden="true" className="relative ml-auto mt-1 h-1.5 w-24 rounded bg-bg-tertiary">
                  <span className="absolute left-1/2 top-0 h-full w-px bg-text-muted/40" />
                  <span className={`absolute top-0 h-full rounded ${s.change_pct >= 0 ? "bg-accent-green" : "bg-accent-red"}`} style={{
                    width: `${Math.abs(s.change_pct) / changeScale * 50}%`,
                    left: `${s.change_pct >= 0 ? 50 : 50 - Math.abs(s.change_pct) / changeScale * 50}%`,
                  }} />
                </div>
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
        <div className="sticky bottom-0 flex justify-center gap-4 border-t border-bg-tertiary bg-bg-secondary/95 px-4 py-3 text-center backdrop-blur">
          {hiddenCount > 0 && <button
            type="button"
            onClick={() => setVisibleCount((value) => Math.min(sectors.length, value + DEFAULT_VISIBLE_SECTOR_COUNT))}
            className="text-xs text-accent-blue hover:underline"
          >
            再显示 {Math.min(hiddenCount, DEFAULT_VISIBLE_SECTOR_COUNT)} 个（剩余 {hiddenCount} 个）
          </button>}
          {visibleCount > DEFAULT_VISIBLE_SECTOR_COUNT && <button type="button" onClick={collapse} className="text-xs text-accent-blue hover:underline">收起，仅显示前 {DEFAULT_VISIBLE_SECTOR_COUNT} 个</button>}
        </div>
      )}
      </div>
    </>
  );
}
