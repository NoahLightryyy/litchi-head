"use client";

import Link from "next/link";

import type { MarketIndex, MarketMeta } from "@/lib/types/market";
import { formatPrice } from "@/lib/utils";
import { MarketDataNotice } from "./market-data-notice";

interface MarketIndicesProps {
  indices: MarketIndex[];
  loading?: boolean;
  error?: boolean;
  meta?: MarketMeta;
  refreshError?: boolean;
  onRetry?: () => void;
}

const sourceNames: Record<string, string> = { sina: "新浪", eastmoney: "东方财富", tencent: "腾讯" };

/** 三大指数卡片 */
export function MarketIndices({ indices, loading, error, meta, refreshError, onRetry }: MarketIndicesProps) {
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

  if (error && !indices.length) {
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
    <>
      <MarketDataNotice meta={meta} refreshError={refreshError} />
      <div className="grid grid-cols-3 gap-4">
        {indices.map((idx) => (
          <MarketIndexCard key={idx.code} index={idx} verifiedSources={idx.cached ? [] : [...new Set(
            meta?.source_diagnostics.filter((source) => source.index_code === idx.code && source.status === "success_data")
              .map((source) => source.upstream_id) ?? [],
          )]} conflicted={meta?.limitations.some(
            (item) => item.index_code === idx.code && ["INDEX_PRICE_CONFLICT", "INDEX_TIMESTAMP_CONFLICT"].includes(item.code),
          )} />
        ))}
      </div>
    </>
  );
}

function MarketIndexCard({ index, conflicted, verifiedSources }: {
  index: MarketIndex; conflicted?: boolean; verifiedSources: string[];
}) {
  const isUp = index.change_pct >= 0;
  const dataTime = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(index.as_of));
  return (
    <Link href={`/index/${index.code === "000001" ? "sh" : "sz"}${index.code}`} aria-label={`查看${index.name}K线`} className="block rounded-lg border border-bg-tertiary bg-bg-secondary p-4 hover:border-accent-blue focus-visible:outline-2 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-muted">{index.code}</span>
        <span className={`text-xs font-medium ${isUp ? "text-accent-green" : "text-accent-red"}`}>
          {isUp ? "▲" : "▼"} {Math.abs(index.change_pct).toFixed(2)}%
        </span>
      </div>
      <div className="text-lg font-number text-text-primary">{formatPrice(index.price)}</div>
      <div className="text-sm text-text-secondary mt-1">{index.name}</div>
      <div className="mt-2 flex flex-wrap gap-x-2 text-[11px] text-text-muted">
        <span>数据时间 {dataTime}</span>
        <span>{conflicted ? "来源冲突" : index.source_count >= 2 ? `${index.source_count} 源一致` : "单源可用"}</span>
        {index.display_source && <span>{sourceNames[index.display_source] ?? index.display_source}</span>}
        {!conflicted && index.source_count >= 2 && verifiedSources.length === index.source_count && (
          <span>{verifiedSources.map((source) => sourceNames[source] ?? source).join("＋")}</span>
        )}
        {index.cached && <span>缓存</span>}
      </div>
    </Link>
  );
}
