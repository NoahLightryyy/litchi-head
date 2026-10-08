"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { sectorHref } from "@/lib/sector-navigation";
import type { MarketMeta, SectorItem } from "@/lib/types/market";
import { formatChangePct, changeColor } from "@/lib/utils";
import {
  sectorPage,
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
  const isSina = sectors.length > 0 && sectors.every((item) => item.source === "sina");
  const flowSort = isSina ? "net_flow" : "fund_flow";
  const heatLabels = { high: "🔥", medium: "📌", low: "—" } as const;
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [jump, setJump] = useState("");
  const view = sectorPage(sectors, query, page);
  const changeScale = sectorChangeScale(sectors);
  const tableContainer = useRef<HTMLDivElement>(null);

  const goToPage = (next: number, revealTable = true) => {
    setPage(sectorPage(sectors, query, next).page);
    setJump("");
    if (revealTable) tableContainer.current?.scrollIntoView({ block: "start" });
  };

  const handleSortChange = (sort: string) => {
    goToPage(1);
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
        <label className="flex items-center gap-2">
          搜索板块
          <input type="search" aria-label="搜索板块名称或代码" placeholder="名称或代码" value={query}
            onChange={(event) => { setQuery(event.target.value); goToPage(1, false); }}
            className="w-44 rounded border border-bg-tertiary bg-bg-secondary px-3 py-2 text-text-primary" />
        </label>
        <span role="status">显示 {view.start}–{view.end} / {view.total} 个板块{query.trim() && `（全榜 ${sectors.length} 个）`}</span>
      </div>
      <div ref={tableContainer} className="overflow-x-auto rounded-lg border border-bg-tertiary bg-bg-secondary">
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
              aria-sort={meta?.sort_applied === flowSort ? "descending" : "none"}
            >
              <button type="button" onClick={() => handleSortChange(flowSort)} className="focus-visible:outline-2 focus-visible:outline-accent-blue">{isSina ? "新浪净流入(亿)" : "主力净流入(亿)"} {meta?.sort_applied === flowSort ? "↓" : ""}</button>
            </th>
            <th className="text-right px-4 py-3 font-medium">热度</th>
          </tr>
        </thead>
        <tbody>
          {view.items.map((s) => {
            const flow = isSina ? s.net_flow ?? null : s.fund_flow;
            return <tr
              key={`${s.id}-${s.rank}`}
              className="border-b border-bg-tertiary last:border-0 hover:bg-bg-tertiary/50 cursor-pointer transition-colors"
            >
              <td className="px-4 py-3 text-text-muted text-xs">{s.rank}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col">
                  <Link href={sectorHref(s)} className="text-text-primary font-medium hover:underline focus-visible:outline-2 focus-visible:outline-accent-blue">{s.name}</Link>
                  <span className="text-xs text-text-muted">
                    {s.category === "industry" ? "行业" : "概念"}{s.source === "sina" && " · 新浪"}
                    {s.top_stocks.length > 0 && ` · ${s.top_stocks.slice(0, 2).join(" · ")}`}
                  </span>
                  <span className="mt-1 text-[11px] text-text-muted">
                    {s.source === "sina"
                      ? `服务更新：${s.service_updated_at?.replace("T", " ") ?? "未知"}（非报价时间）`
                      : `行情时间：${s.as_of?.replace("T", " ") ?? "未知"}`}
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
              <td className={`px-4 py-3 text-right font-number ${flow === null ? "text-text-muted" : flow >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {flow === null ? "—" : `${flow >= 0 ? "+" : ""}${flow.toFixed(1)}`}
              </td>
              <td className="px-4 py-3 text-right">{isSina ? "—" : heatLabels[s.heat]}</td>
            </tr>;
          })}
        </tbody>
      </table>
      </div>
      {view.total === 0 && <p className="py-4 text-center text-sm text-text-muted" role="status">未找到匹配的板块，请更换名称或代码</p>}
      <nav aria-label="板块分页" className="flex flex-wrap items-center justify-center gap-2 rounded-b-lg border border-bg-tertiary bg-bg-secondary px-3 py-3 text-xs">
        {[
          { label: "首页", target: 1, disabled: view.page === 1 },
          { label: "上一页", target: view.page - 1, disabled: view.page === 1 },
          { label: "下一页", target: view.page + 1, disabled: view.page === view.pageCount },
          { label: "尾页", target: view.pageCount, disabled: view.page === view.pageCount },
        ].map(({ label, target, disabled }) => <button key={label} type="button" disabled={disabled}
          onClick={() => goToPage(target)} className="rounded border border-bg-tertiary px-3 py-2 text-accent-blue hover:bg-bg-tertiary disabled:cursor-not-allowed disabled:opacity-40">{label}</button>)}
        <span aria-live="polite">第 {view.page} / {view.pageCount} 页</span>
        <form className="flex items-center gap-2" onSubmit={(event) => { event.preventDefault(); if (jump.trim()) goToPage(Number(jump)); }}>
          <label className="flex items-center gap-2">跳至
            <input aria-label="跳转页码" type="number" min={1} max={view.pageCount} step={1} value={jump}
              onChange={(event) => setJump(event.target.value)} className="w-16 rounded border border-bg-tertiary bg-bg-primary px-2 py-2" />页
          </label>
          <button type="submit" disabled={!jump.trim() || !view.total} className="rounded border border-bg-tertiary px-3 py-2 text-accent-blue disabled:opacity-40">跳转</button>
        </form>
      </nav>
    </>
  );
}
