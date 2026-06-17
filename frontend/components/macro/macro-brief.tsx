"use client";

import { RefreshCw } from "lucide-react";
import type { MacroBrief as MacroBriefType } from "@/lib/types/market";

interface MacroBriefProps {
  brief: MacroBriefType | null;
  loading?: boolean;
  error?: boolean;
  onRefresh?: () => void;
}

/** AI 宏观简报卡片 */
export function MacroBrief({ brief, loading, error, onRefresh }: MacroBriefProps) {
  if (error && !loading) {
    return (
      <div className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-4 text-center">
        <p className="text-sm text-text-muted mb-2">宏观简报生成失败</p>
        {onRefresh && (
          <button onClick={onRefresh} className="text-xs text-accent-blue hover:underline">重新加载</button>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary">AI 宏观简报</h3>
        <span className="text-xs text-text-muted">自动生成 · 仅供参考</span>
      </div>

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
          <RefreshCw className="w-3 h-3" /> 刷新分析
        </button>
      )}
    </div>
  );
}
