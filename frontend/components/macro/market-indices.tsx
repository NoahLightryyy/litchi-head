"use client";

import type { MarketIndex } from "@/lib/types/market";
import { formatPrice, formatChangePct } from "@/lib/utils";

interface MarketIndicesProps {
  indices: MarketIndex[];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
}

/** 三大指数卡片 */
export function MarketIndices({ indices, loading, error, onRetry }: MarketIndicesProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 animate-pulse">
            <div className="h-3 w-16 bg-bg-tertiary rounded mb-2" />
            <div className="h-8 w-24 bg-bg-tertiary rounded mb-2" />
            <div className="h-3 w-12 bg-bg-tertiary rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-4 text-center">
        <p className="text-sm text-text-muted mb-2">指数数据加载失败</p>
        {onRetry && (
          <button onClick={onRetry} className="text-xs text-accent-blue hover:underline">
            重新加载
          </button>
        )}
      </div>
    );
  }

  if (!indices.length) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 text-center">
        <p className="text-xs text-text-muted">暂无指数数据</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-4">
      {indices.map((idx) => (
        <MarketIndexCard key={idx.code} index={idx} />
      ))}
    </div>
  );
}

function MarketIndexCard({ index }: { index: MarketIndex }) {
  const isUp = index.change_pct >= 0;
  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 hover:border-bg-elevated transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-muted">{index.code}</span>
        <span className={`text-xs font-medium ${isUp ? "text-accent-green" : "text-accent-red"}`}>
          {isUp ? "▲" : "▼"} {Math.abs(index.change_pct).toFixed(2)}%
        </span>
      </div>
      <div className="text-lg font-number text-text-primary">{formatPrice(index.price)}</div>
      <div className="text-sm text-text-secondary mt-1">{index.name}</div>
    </div>
  );
}
