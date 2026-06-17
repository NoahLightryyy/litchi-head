"use client";

import { BrainCircuit, RefreshCw } from "lucide-react";

interface ChainAnalysisProps {
  analysis: string | null;
  loading?: boolean;
  onRefresh?: () => void;
}

/** AI 产业链分析摘要卡片 */
export function ChainAnalysis({ analysis, loading, onRefresh }: ChainAnalysisProps) {
  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      <div className="flex items-center gap-2 mb-3">
        <BrainCircuit className="w-4 h-4 text-accent-blue" />
        <h3 className="text-sm font-semibold text-text-primary">AI 产业链分析</h3>
        <span className="text-xs text-text-muted ml-auto">自动生成</span>
      </div>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-3 w-full bg-bg-tertiary rounded" />
          <div className="h-3 w-5/6 bg-bg-tertiary rounded" />
        </div>
      ) : analysis ? (
        <p className="text-sm text-text-secondary leading-relaxed">{analysis}</p>
      ) : (
        <p className="text-sm text-text-muted text-center py-4">暂无分析数据</p>
      )}

      {onRefresh && (
        <button
          onClick={onRefresh}
          className="mt-3 w-full py-2 rounded-md bg-accent-blue/10 text-accent-blue text-sm font-medium hover:bg-accent-blue/20 transition-colors flex items-center justify-center gap-2"
        >
          <RefreshCw className="w-3 h-3" /> 刷新分析
        </button>
      )}
    </div>
  );
}
