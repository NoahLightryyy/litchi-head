"use client";

import { RefreshCw } from "lucide-react";
import type { MacroBrief as MacroBriefType } from "@/lib/types/market";
import type { MarketMeta } from "@/lib/types/market";
import { MarketDataNotice } from "./market-data-notice";

interface MacroBriefProps {
  brief: MacroBriefType | null;
  loading?: boolean;
  error?: boolean;
  meta?: MarketMeta;
  refreshError?: boolean;
  onRefresh?: () => void;
}

/** 指数摘要卡片 */
export function MacroBrief({ brief, loading, error, meta, refreshError, onRefresh }: MacroBriefProps) {
  if (error && !loading && !brief) {
    return (
      <div className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-4 text-center">
        <p className="text-sm text-text-muted mb-2">指数摘要加载失败</p>
        {onRefresh && (
          <button onClick={onRefresh} className="text-xs text-accent-blue hover:underline">重新加载</button>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      <MarketDataNotice meta={meta} refreshError={refreshError} />


      <p className="text-xs text-text-muted mb-3">按指数行情自动汇总，未调用 AI 分析。</p>
      {loading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-3 w-full bg-bg-tertiary rounded" />
          <div className="h-3 w-5/6 bg-bg-tertiary rounded" />
          <div className="h-3 w-4/6 bg-bg-tertiary rounded" />
        </div>
      ) : brief ? (
        <>
          <p className="text-sm text-text-secondary leading-relaxed">{brief.summary}</p>
          {brief.risk_tips.length > 0 && (
            <div className="mt-3 pt-3 border-t border-bg-tertiary">
              <span className="text-xs text-accent-gold font-medium">⚠ 风险提示：</span>
              <ul className="mt-1 space-y-1">
                {brief.risk_tips.map((tip, i) => (
                  <li key={i} className="text-xs text-text-secondary">· {tip}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-text-muted text-center py-4">暂无数据</p>
      )}

      {onRefresh && (
        <button
          onClick={onRefresh}
          className="mt-4 w-full py-2 rounded-md bg-accent-blue/10 text-accent-blue text-sm font-medium hover:bg-accent-blue/20 transition-colors flex items-center justify-center gap-2"
        >
          <RefreshCw className="w-3 h-3" /> 刷新数据
        </button>
      )}
    </div>
  );
}
