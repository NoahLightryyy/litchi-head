"use client";

import { useState } from "react";
import { useSectors } from "@/lib/hooks/use-market";
import { SectorRanking } from "./sector-ranking";

function FundingPanel({ source, category }: {
  source: "eastmoney" | "sina";
  category: string;
}) {
  const isSina = source === "sina";
  const title = isSina ? "新浪 · 净流入" : "东方财富 · 主力净流入";
  const [sort, setSort] = useState(isSina ? "net_flow" : "fund_flow");
  const query = useSectors(sort, source);
  const items = query.data?.data ?? [];
  const filtered = category === "all" ? items : items.filter(item => item.category === category);
  const failedCategory = query.data?.meta.failed_sources.includes(category) ?? false;
  const applied = query.data?.meta.sort_applied;
  const sortLabel = applied === "change_pct" ? "按涨跌幅排序"
    : applied === "fund_flow" ? "按主力净流入排序"
    : applied === "net_flow" ? "按新浪净流入排序"
    : query.data ? "按来源顺序" : "";

  return <section aria-label={title} className="min-w-0 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold text-text-primary">{title}</h3>
      <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching}
        className="rounded border border-bg-tertiary px-3 py-2 text-xs text-accent-blue disabled:opacity-50">
        {query.isFetching ? "加载中…" : "刷新此来源"}
      </button>
    </div>
    <p className="text-xs text-text-muted">{isSina
      ? "新浪原生分类；净流入按新浪口径，服务更新时间不代表逐板块报价时间。"
      : "东方财富行业与概念分类；主力净流入按东方财富口径，历史快照保留数据时间。"}</p>
    {sortLabel && <p className="text-xs text-text-muted">{sortLabel}</p>}
    <SectorRanking key={category} sectors={filtered} loading={query.isLoading}
      error={query.isError || failedCategory} meta={query.data?.meta}
      refreshError={query.isError && !!query.data}
      onRetry={() => void query.refetch()} onSortChange={setSort} />
  </section>;
}

/** No audited cross-provider membership mapping exists: keep both native taxonomies. */
export function SectorFundingPanels({ category = "all" }: { category?: string }) {
  return <div className="space-y-4">
    <p className="text-sm text-text-muted">同时查看主力净流入与新浪净流入。两源板块定义尚未核验对应关系，同名板块不直接合并，金额不相加或相减。</p>
    <div className="grid grid-cols-1 gap-6 2xl:grid-cols-2">
      <FundingPanel source="eastmoney" category={category} />
      <FundingPanel source="sina" category={category} />
    </div>
  </div>;
}
