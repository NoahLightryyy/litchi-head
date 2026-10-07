"use client";

import { useCallback } from "react";
import { BarChart3, TrendingUp, Newspaper } from "lucide-react";
import { useMarketIndices, useMacroBrief, useHotNews } from "@/lib/hooks/use-market";
import { StockDiscovery } from "@/components/shared/stock-discovery";
import { MarketIndices } from "@/components/macro/market-indices";
import { SectorFundingPanels } from "@/components/macro/sector-funding-panels";
import { MacroBrief } from "@/components/macro/macro-brief";
import { MarketDataNotice } from "@/components/macro/market-data-notice";
import { NewsArchive } from "@/components/macro/news-archive";
import { NewsTopics } from "@/components/macro/news-topics";

/** 宏观总览主页面 */
export default function MacroPage() {


  // ── 数据 ──
  const indicesQuery = useMarketIndices();
  const briefQuery = useMacroBrief();
  const newsQuery = useHotNews();


  const handleRefreshBrief = useCallback(() => {
    void briefQuery.refetch();
  }, [briefQuery]);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <StockDiscovery />

      {/* 指数卡片 */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-accent-blue" />
          <h2 className="text-sm font-semibold text-text-primary">三大指数</h2>
        </div>
        <MarketIndices
          indices={indicesQuery.data?.data ?? []}
          loading={indicesQuery.isLoading}
          error={indicesQuery.isError}
          refreshError={indicesQuery.isError && !!indicesQuery.data}
          meta={indicesQuery.data?.meta}
          onRetry={() => void indicesQuery.refetch()}
        />
      </section>

      {/* 双来源资金榜单与指数摘要 */}
      <div className="flex flex-col gap-6">
        {/* 板块排行 */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4 text-accent-blue" />
            <h2 className="text-sm font-semibold text-text-primary">板块排行榜</h2>
          </div>
          <SectorFundingPanels />
        </section>

        {/* 指数摘要 */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-accent-blue" />
            <h2 className="text-sm font-semibold text-text-primary">指数摘要</h2>
            <span className="text-xs text-text-muted ml-auto">自动生成</span>
          </div>
          <MacroBrief
            brief={briefQuery.data?.data ?? null}
            loading={briefQuery.isLoading}
            error={briefQuery.isError}
            refreshError={briefQuery.isError && !!briefQuery.data}
            meta={briefQuery.data?.meta}
            onRefresh={handleRefreshBrief}
          />
        </section>
      </div>

      {/* 热点快讯 */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Newspaper className="w-4 h-4 text-accent-blue" />
          <h2 className="text-sm font-semibold text-text-primary">热点快讯</h2>
          <span className="text-xs text-text-muted ml-auto">主题提取 · 点击词云查看报道</span>
        </div>
        <div className="rounded-lg border border-bg-tertiary bg-bg-secondary divide-y divide-bg-tertiary">
          {newsQuery.isLoading ? (
            <div className="p-4 space-y-3">
              {[1,2,3].map((i) => (
                <div key={i} className="h-4 bg-bg-tertiary rounded animate-pulse" />
              ))}
            </div>
          ) : newsQuery.isError && !newsQuery.data ? (
            <div className="p-4 text-center">
              <p className="text-sm text-text-muted mb-2">热点快讯加载失败</p>
              <button onClick={() => void newsQuery.refetch()} className="text-xs text-accent-blue hover:underline">重新加载</button>
            </div>
          ) : newsQuery.data && newsQuery.data.data.length > 0 ? (
            <div>
              <div className="px-4 pt-3">
                <MarketDataNotice meta={newsQuery.data.meta} refreshError={newsQuery.isError} />
              </div>
              <NewsTopics items={newsQuery.data.data} sampledAt={newsQuery.dataUpdatedAt} refreshFailed={newsQuery.isError} />
            </div>
          ) : (
            <div className="p-4">
              <p className="text-xs text-text-muted text-center py-4">暂无实时快讯</p>
            </div>
          )}
        </div>
      </section>
      <NewsArchive />
    </div>
  );
}
