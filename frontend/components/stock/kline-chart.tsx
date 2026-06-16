"use client";

import { useState, useCallback } from "react";
import { useKline } from "@/lib/hooks/use-stock";
import { CandlestickChart } from "@/components/stock/candlestick-chart";

interface KlineChartProps {
  code: string;
}

const PERIOD_MAP = [
  { label: "日线", value: "daily" },
  { label: "周线", value: "weekly" },
  { label: "月线", value: "monthly" },
] as const;

/**
 * K 线图容器
 *
 * 管理周期切换 + 数据获取，将数据传给 CandlestickChart 渲染。
 * 自包含 — 只需传入股票 code。
 */
export function KlineChart({ code }: KlineChartProps) {
  const [period, setPeriod] = useState<string>("daily");

  const { data: klines, isLoading, isError } = useKline(code, period);

  const handlePeriodChange = useCallback((value: string) => {
    setPeriod(value);
  }, []);

  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
      {/* 工具栏 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text-primary">K 线图</h2>
        <div className="flex items-center gap-2">
          {/* 周期切换 */}
          <div className="flex gap-1 bg-bg-tertiary rounded-md p-0.5">
            {PERIOD_MAP.map((p) => (
              <button
                key={p.value}
                onClick={() => handlePeriodChange(p.value)}
                className={`px-3 py-1 text-xs rounded ${
                  period === p.value
                    ? "bg-accent-blue text-white"
                    : "text-text-secondary hover:text-text-primary"
                } transition-colors`}
              >
                {p.label}
              </button>
            ))}
          </div>
          {/* 指标切换（占位） */}
          <button className="px-3 py-1 text-xs rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors">
            + 指标
          </button>
        </div>
      </div>

      {/* 图表区 */}
      {isLoading ? (
        <div className="h-80 rounded-md bg-bg-primary flex items-center justify-center border border-bg-tertiary">
          <div className="text-sm text-text-muted animate-pulse">加载中...</div>
        </div>
      ) : isError ? (
        <div className="h-80 rounded-md bg-bg-primary flex items-center justify-center border border-bg-tertiary">
          <div className="text-center">
            <div className="text-2xl mb-2">⚠️</div>
            <p className="text-sm text-text-muted">数据加载失败</p>
          </div>
        </div>
      ) : klines && klines.length > 0 ? (
        <CandlestickChart data={klines} />
      ) : (
        <div className="h-80 rounded-md bg-bg-primary flex items-center justify-center border border-bg-tertiary">
          <div className="text-center">
            <div className="text-2xl mb-2">📭</div>
            <p className="text-sm text-text-muted">暂无数据</p>
          </div>
        </div>
      )}
    </div>
  );
}
