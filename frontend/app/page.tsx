"use client";

import { useState, useCallback } from "react";
import { Search, BarChart3, TrendingUp, Newspaper } from "lucide-react";
import { useMarketIndices, useSectors, useMacroBrief } from "@/lib/hooks/use-market";
import { useStockSearch } from "@/lib/hooks/use-stock";
import { MarketIndices } from "@/components/macro/market-indices";
import { SectorRanking } from "@/components/macro/sector-ranking";
import { MacroBrief } from "@/components/macro/macro-brief";

/** 宏观总览主页面 */
export default function MacroPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("fund_flow");

  // ── 数据 ──
  const { data: indices, isLoading: idxLoading, isError: idxError } = useMarketIndices();
  const { data: sectors, isLoading: secLoading, isError: secError } = useSectors(sortBy);
  const { data: brief, isLoading: briefLoading, isError: briefError, refetch } = useMacroBrief();
  const { data: searchResults } = useStockSearch(searchQuery);

  const handleSortChange = useCallback((sort: string) => {
    setSortBy(sort);
  }, []);

  const handleRefreshBrief = useCallback(() => {
    refetch();
  }, [refetch]);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {/* 搜索框 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索股票代码、名称或板块..."
          className="w-full h-10 pl-10 pr-4 rounded-lg bg-bg-secondary border border-bg-tertiary text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-blue text-sm"
        />
        {searchQuery.length >= 2 && searchResults && searchResults.length > 0 && (
          <div className="absolute top-full mt-1 w-full rounded-lg border border-bg-tertiary bg-bg-secondary shadow-lg z-10 overflow-hidden">
            {searchResults.map((r) => (
              <a
                key={r.code}
                href={`/stock/${r.code}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-bg-tertiary/50 transition-colors border-b border-bg-tertiary last:border-0"
              >
                <span className="text-sm font-medium text-text-primary">{r.name}</span>
                <span className="text-xs text-text-muted">{r.code}</span>
                <span className="text-xs text-accent-blue ml-auto">{r.type}</span>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* 指数卡片 */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-accent-blue" />
          <h2 className="text-sm font-semibold text-text-primary">三大指数</h2>
        </div>
        <MarketIndices indices={indices ?? []} loading={idxLoading} error={idxError} />
      </section>

      {/* 两列布局：板块排行 + AI 简报 */}
      <div className="grid grid-cols-3 gap-6">
        {/* 板块排行 */}
        <section className="col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4 text-accent-blue" />
            <h2 className="text-sm font-semibold text-text-primary">板块排行榜</h2>
            <span className="text-xs text-text-muted ml-auto">按主力资金流向排序</span>
          </div>
          <SectorRanking
            sectors={sectors ?? []}
            loading={secLoading}
            error={secError}
            sortBy={sortBy}
            onSortChange={handleSortChange}
          />
        </section>

        {/* AI 宏观简报 */}
        <section className="col-span-1">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-accent-blue" />
            <h2 className="text-sm font-semibold text-text-primary">AI 宏观简报</h2>
            <span className="text-xs text-text-muted ml-auto">自动生成</span>
          </div>
          <MacroBrief
            brief={brief ?? null}
            loading={briefLoading}
            error={briefError}
            onRefresh={handleRefreshBrief}
          />
        </section>
      </div>

      {/* 热点快讯 */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Newspaper className="w-4 h-4 text-accent-blue" />
          <h2 className="text-sm font-semibold text-text-primary">热点快讯</h2>
          <span className="text-xs text-text-muted ml-auto">实时市场动态</span>
        </div>
        <div className="p-4 rounded-lg border border-bg-tertiary bg-bg-secondary">
          <p className="text-xs text-text-muted text-center py-4">暂无实时快讯（待接入数据源）</p>
        </div>
      </section>
    </div>
  );
}
