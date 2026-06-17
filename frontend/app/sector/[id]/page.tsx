"use client";

import { useParams } from "next/navigation";
import { ArrowLeft, Network, List, BrainCircuit } from "lucide-react";
import { useSectorDetail } from "@/lib/hooks/use-market";
import { SectorHeader } from "@/components/sector/sector-header";
import { ChainMap } from "@/components/sector/chain-map";
import { ChainAnalysis } from "@/components/sector/chain-analysis";
import { StockList } from "@/components/sector/stock-list";

/** 板块详情 / 产业链分析页 */
export default function SectorPage() {
  const params = useParams();
  const sectorId = params.id as string;
  const { data: sector, isLoading, error } = useSectorDetail(sectorId);

  // ── 加载态 ──
  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-7xl mx-auto animate-pulse">
        <div className="h-4 w-40 bg-bg-tertiary rounded" />
        <div className="h-8 w-60 bg-bg-tertiary rounded" />
        <div className="grid grid-cols-5 gap-6">
          <div className="col-span-3 h-80 bg-bg-tertiary rounded" />
          <div className="col-span-2 space-y-4">
            <div className="h-32 bg-bg-tertiary rounded" />
            <div className="h-48 bg-bg-tertiary rounded" />
          </div>
        </div>
      </div>
    );
  }

  // ── 错误/空态 ──
  if (error || !sector) {
    return (
      <div className="flex flex-col gap-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2 text-sm">
          <a href="/" className="text-text-secondary hover:text-text-primary transition-colors">
            宏观总览
          </a>
          <span className="text-text-muted">/</span>
          <span className="text-text-muted">板块未找到</span>
        </div>
        <div className="p-8 rounded-lg border border-bg-tertiary bg-bg-secondary text-center">
          <div className="text-4xl mb-4">📡</div>
          <p className="text-sm text-text-muted mb-2">板块数据加载失败</p>
          <p className="text-xs text-text-muted mb-4">数据源可能暂时不可用，请稍后重试</p>
          <div className="flex items-center justify-center gap-3">
            <a
              href="/"
              className="px-4 py-2 rounded-md bg-bg-tertiary text-text-secondary text-sm font-medium hover:bg-bg-elevated transition-colors"
            >
              返回宏观总览
            </a>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 transition-colors"
            >
              重新加载
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {/* 面包屑 */}
      <div className="flex items-center gap-2 text-sm">
        <a href="/" className="text-text-secondary hover:text-text-primary transition-colors">
          宏观总览
        </a>
        <span className="text-text-muted">/</span>
        <span className="text-text-primary font-medium">{sector.name}</span>
      </div>

      {/* 板块头部 */}
      <div className="flex items-center justify-between">
        <SectorHeader
          name={sector.name}
          changePct={sector.change_pct}
          fundFlow={sector.fund_flow}
          heat={sector.heat as "high" | "medium" | "low"}
        />
        <a
          href="/"
          className="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-3 h-3" /> 返回
        </a>
      </div>

      {/* 两列布局 */}
      <div className="grid grid-cols-5 gap-6">
        {/* 左列：产业链地图 (3/5) */}
        <div className="col-span-3">
          <div className="flex items-center gap-2 mb-3">
            <Network className="w-4 h-4 text-accent-blue" />
            <h2 className="text-sm font-semibold text-text-primary">产业链地图</h2>
            <span className="text-xs text-text-muted ml-auto">上下游关键节点</span>
          </div>
          <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
            <ChainMap stages={sector.chain_map} />
          </div>
        </div>

        {/* 右列：个股排行 + AI 分析 (2/5) */}
        <div className="col-span-2 flex flex-col gap-4">
          {/* AI 产业链分析 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BrainCircuit className="w-4 h-4 text-accent-blue" />
              <h2 className="text-sm font-semibold text-text-primary">AI 产业链分析</h2>
              <span className="text-xs text-text-muted ml-auto">自动生成</span>
            </div>
            <ChainAnalysis analysis={sector.ai_analysis || null} />
          </div>

          {/* 板块个股列表 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <List className="w-4 h-4 text-accent-blue" />
              <h2 className="text-sm font-semibold text-text-primary">板块个股</h2>
              <span className="text-xs text-text-muted ml-auto">按 AI 评级排序</span>
            </div>
            <StockList stocks={sector.stocks} />
          </div>
        </div>
      </div>
    </div>
  );
}
