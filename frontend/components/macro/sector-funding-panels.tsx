"use client";

import { useState } from "react";
import { useSectors } from "@/lib/hooks/use-market";
import { preferredSectorSource, sectorCategoryMeta, sectorFeedPriority } from "@/lib/sector-availability";
import { SectorRanking } from "./sector-ranking";

function FundingPanel({ source, category, query, onSortChange }: {
  source: "eastmoney" | "sina";
  category: string;
  query: ReturnType<typeof useSectors>;
  onSortChange: (sort: string) => void;
}) {
  const isSina = source === "sina";
  const title = isSina ? "新浪 · 净流入" : "东方财富 · 主力净流入";
  const items = query.data?.data ?? [];
  const filtered = category === "all" ? items : items.filter(item => item.category === category);
  const meta = sectorCategoryMeta(query.data?.meta, category);
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
    {sortLabel && <p className="text-xs text-text-muted">{sortLabel}</p>}
    <SectorRanking key={category} sectors={filtered} loading={query.isLoading}
      error={query.isError || failedCategory} meta={meta}
      refreshError={query.isError && !!query.data}
      paused={query.isPaused}
      onRetry={() => void query.refetch()} onSortChange={onSortChange} />
  </section>;
}

/** No audited cross-provider membership mapping exists: keep both native taxonomies. */
export function SectorFundingPanels({ category = "all" }: { category?: string }) {
  const [eastSort, setEastSort] = useState("fund_flow");
  const [sinaSort, setSinaSort] = useState("net_flow");
  const eastmoney = useSectors(eastSort, "eastmoney");
  const sina = useSectors(sinaSort, "sina");
  const first = preferredSectorSource(eastmoney, sina, category);
  const sources = first === "sina" ? ["sina", "eastmoney"] as const : ["eastmoney", "sina"] as const;
  const alternativeAvailable = first === "sina" && sectorFeedPriority(sina, category) === 0 && sectorFeedPriority(eastmoney, category) >= 2;
  return <div className="space-y-4">
    <p className="text-sm text-text-muted">{alternativeAvailable && "优先展示已获取的新浪榜单。"}两源按各自分类和资金口径独立展示。</p>
    <div className="grid grid-cols-1 gap-6 2xl:grid-cols-2">
      {sources.map(source => <FundingPanel key={source} source={source} category={category}
        query={source === "sina" ? sina : eastmoney}
        onSortChange={source === "sina" ? setSinaSort : setEastSort} />)}
    </div>
  </div>;
}
