"use client";

import { useCapitalFlow } from "@/lib/hooks/use-stock";
import type { CapitalFlow } from "@/lib/types/stock";

interface CapitalFlowPanelProps {
  code: string;
}

/** 资金流向面板：主力/散户/机构净流入趋势 */
export function CapitalFlowPanel({ code }: CapitalFlowPanelProps) {
  const { data, isLoading, error } = useCapitalFlow(code);

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-6 rounded bg-bg-tertiary" />
        ))}
      </div>
    );
  }

  if (error || !data || data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-3xl mb-3">💰</div>
        <p className="text-sm text-text-muted">暂无资金流向数据</p>
      </div>
    );
  }

  // 取最近 10 条
  const recent = data.slice(-10);

  // 计算汇总
  const latest = recent[recent.length - 1];
  const totals = recent.reduce(
    (acc, item) => ({
      main: acc.main + item.main_net_inflow,
      retail: acc.retail + item.retail_net_inflow,
      institutional: acc.institutional + item.institutional_net_inflow,
    }),
    { main: 0, retail: 0, institutional: 0 }
  );

  return (
    <div className="space-y-5">
      {/* 汇总卡片 */}
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard
          label="主力净流入"
          value={totals.main}
          colorClass="text-accent-red"
        />
        <SummaryCard
          label="机构净流入（大单）"
          value={totals.institutional}
          colorClass="text-accent-blue"
        />
        <SummaryCard
          label="散户净流入（小单）"
          value={totals.retail}
          colorClass="text-accent-gold"
        />
      </div>

      {/* 最近资金流水 */}
      <div>
        <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">
          近期明细
        </h4>
        <div className="space-y-1">
          <div className="grid grid-cols-4 gap-2 text-xs text-text-muted px-2 py-1">
            <span>日期</span>
            <span className="text-right">主力</span>
            <span className="text-right">机构</span>
            <span className="text-right">散户</span>
          </div>
          {recent.reverse().map((item) => (
            <div
              key={item.date}
              className="grid grid-cols-4 gap-2 text-xs px-2 py-1.5 rounded hover:bg-bg-tertiary/50 transition-colors"
            >
              <span className="text-text-secondary">{item.date}</span>
              <FlowValue value={item.main_net_inflow} />
              <FlowValue value={item.institutional_net_inflow} />
              <FlowValue value={item.retail_net_inflow} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── 子组件 ── */

function SummaryCard({
  label,
  value,
  colorClass,
}: {
  label: string;
  value: number;
  colorClass: string;
}) {
  const absValue = Math.abs(value);
  const displayValue =
    absValue >= 1_000_000_000
      ? `${(value / 1_000_000_000).toFixed(2)}亿`
      : absValue >= 10_000
        ? `${(value / 10_000).toFixed(0)}万`
        : value.toFixed(0);

  return (
    <div className="p-3 rounded-md border border-bg-tertiary bg-bg-primary/50">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`font-number text-sm font-semibold ${colorClass}`}>
        {value >= 0 ? "+" : ""}{displayValue}
      </div>
    </div>
  );
}

function FlowValue({ value }: { value: number }) {
  const color =
    value > 0
      ? "text-accent-red"
      : value < 0
        ? "text-accent-green"
        : "text-text-muted";
  return <span className={`text-right font-number ${color}`}>{value > 0 ? "+" : ""}{value.toFixed(0)}</span>;
}
