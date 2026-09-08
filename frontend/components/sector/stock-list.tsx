"use client";

import { useState } from "react";
import Link from "next/link";
import type { SectorStock } from "@/lib/types/market";

interface StockListProps {
  stocks: SectorStock[];
  loading?: boolean;
}

/** 板块个股列表（可点击跳转到个股决策页） */
export function StockList({ stocks, loading }: StockListProps) {
  const [movement, setMovement] = useState("all");
  const [flow, setFlow] = useState("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const filtered = stocks.filter((stock) => {
    const text = query.trim().toLowerCase();
    return (!text || stock.name.toLowerCase().includes(text) || stock.code.includes(text)) &&
      (movement === "all" || (movement === "up" ? stock.change_pct > 0 : movement === "down" ? stock.change_pct < 0 : stock.change_pct === 0)) &&
      (flow === "all" || (flow === "unknown" ? stock.fund_flow === null : stock.fund_flow !== null &&
        (flow === "in" ? stock.fund_flow > 0 : flow === "out" ? stock.fund_flow < 0 : stock.fund_flow === 0)));
  }).sort((a, b) => b.change_pct - a.change_pct || a.code.localeCompare(b.code));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * 10, current * 10);
  if (loading) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-bg-tertiary/50 border-b border-bg-tertiary animate-pulse" />
        ))}
      </div>
    );
  }

  if (stocks.length === 0) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-8 text-center">
        <p className="text-sm text-text-muted">暂无板块个股</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden">
      <div className="p-3 space-y-3 border-b border-bg-tertiary">
        <p className="text-xs text-text-muted">行情维度：当日涨跌、主力净流入。盈利、估值、成长、风险及产业位置尚未纳入本表，暂无综合评级。</p>
        <details className="text-xs text-text-muted leading-relaxed">
          <summary className="cursor-pointer text-accent-blue">指标与原评级口径</summary>
          <p className="mt-2">原 A/B 等级只按单日涨跌计算：A ≥5%；B+ ≥2%且&lt;5%；B ≥0%且&lt;2%；C ≥−3%且&lt;0%；D &lt;−3%。不属于AI研究评级，现已取消展示。</p>
          <p className="mt-2">涨跌按正、负、零分类；主力净流入按正、负、零及未知分类，单位亿元，沿用数据源统计口径。净流入不等于公司盈利；上涨不代表低估或值得买入。数据时间见本页行情快照提示。</p>
        </details>
        <input aria-label="搜索板块个股" placeholder="搜索名称或代码" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} className="w-full rounded border border-bg-tertiary bg-bg-primary px-2 py-2 text-sm" />
        <div className="flex flex-wrap gap-2 text-xs">
          <label>涨跌分类 <select aria-label="涨跌分类" value={movement} onChange={(event) => { setMovement(event.target.value); setPage(1); }} className="rounded border border-bg-tertiary bg-bg-primary p-1">
            <option value="all">全部</option><option value="up">上涨</option><option value="down">下跌</option><option value="flat">平盘</option>
          </select></label>
          <label>资金分类 <select aria-label="资金分类" value={flow} onChange={(event) => { setFlow(event.target.value); setPage(1); }} className="rounded border border-bg-tertiary bg-bg-primary p-1">
            <option value="all">全部</option><option value="in">净流入</option><option value="out">净流出</option><option value="zero">零值</option><option value="unknown">未知</option>
          </select></label>
        </div>
        <p className="text-xs text-text-muted">符合 {filtered.length} / {stocks.length} 只 · 按当日涨跌幅降序</p>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-bg-tertiary text-text-muted text-xs uppercase tracking-wider">
            <th className="text-left px-3 py-2 font-medium">名称</th>
            <th className="text-right px-3 py-2 font-medium">涨跌</th>
            <th className="text-right px-3 py-2 font-medium">资金(亿)</th>

          </tr>
        </thead>
        <tbody>
          {visible.map((s) => (
            <tr key={s.code} className="border-b border-bg-tertiary last:border-0 hover:bg-bg-tertiary/50 transition-colors">
              <td className="px-3 py-2.5">
                <Link
                  href={`/stock/${s.code}`}
                  className="flex flex-col rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue"
                  aria-label={`查看 ${s.name}（${s.code}）的个股决策`}
                >
                  <span className="text-text-primary font-medium">{s.name}</span>
                  <span className="text-xs text-text-muted">{s.code}</span>
                </Link>
              </td>
              <td className={`px-3 py-2.5 text-right font-number ${s.change_pct >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(2)}%
              </td>
              <td className={`px-3 py-2.5 text-right font-number ${s.fund_flow === null ? "text-text-muted" : s.fund_flow >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                {s.fund_flow === null ? "—" : `${s.fund_flow >= 0 ? "+" : ""}${s.fund_flow.toFixed(1)}`}
              </td>

            </tr>
          ))}
        </tbody>
      </table>
      {filtered.length === 0 && <p className="p-4 text-center text-sm text-text-muted">没有符合筛选条件的个股</p>}
      <div className="flex flex-wrap justify-center items-center gap-2 border-t border-bg-tertiary p-3 text-xs">
        <button disabled={current === 1} onClick={() => setPage(1)} className="disabled:opacity-40">首页</button>
        <button disabled={current === 1} onClick={() => setPage(current - 1)} className="disabled:opacity-40">上一页</button>
        <span>{current} / {pages} 页</span>
        <button disabled={current === pages} onClick={() => setPage(current + 1)} className="disabled:opacity-40">下一页</button>
        <button disabled={current === pages} onClick={() => setPage(pages)} className="disabled:opacity-40">尾页</button>
        <label>跳至 <select aria-label="跳至个股页码" value={current} onChange={(event) => setPage(Number(event.target.value))} className="rounded border border-bg-tertiary bg-bg-primary p-1">{Array.from({length: pages}, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select></label>
      </div>
    </div>
  );
}
