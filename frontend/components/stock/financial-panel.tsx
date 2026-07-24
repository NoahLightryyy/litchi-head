"use client";

import { useFinancials, useValuation, useIndicators } from "@/lib/hooks/use-stock";
import type { FinancialMetrics, ValuationMetrics, DynamicIndicators } from "@/lib/types/stock";

interface FinancialPanelProps {
  code: string;
}

/** 财务分析面板：财务指标 + 估值比率 + 行业感知过滤 */
export function FinancialPanel({ code }: FinancialPanelProps) {
  const { data: financials, isLoading: finLoading, isError: finError } = useFinancials(code);
  const { data: valuation, isLoading: valLoading, isError: valError } = useValuation(code);
  const { data: indicators, isLoading: indLoading } = useIndicators(code);

  const loading = finLoading || valLoading || indLoading;
  const error = finError && valError;

  // ── 加载态 ──
  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-lg bg-bg-tertiary" />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 rounded-lg bg-bg-tertiary" />
          ))}
        </div>
      </div>
    );
  }

  // ── 空态 / 错误态 ──
  if (error || (!financials?.length && !valuation)) {
    return (
      <div className="text-center py-8">
        <div className="text-3xl mb-3">🏛️</div>
        <p className="text-sm text-text-muted">暂无财务数据</p>
        <p className="text-xs text-text-muted mt-1">财务指标数据暂不可用</p>
      </div>
    );
  }

  const latest = financials?.[0];
  const relevantIds = new Set(indicators?.indicator_ids ?? []);

  return (
    <div className="space-y-5">
      {/* 行业标签 */}
      {indicators?.industry && (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-accent-blue bg-accent-blue/10 px-2.5 py-1 rounded-full">
            {indicators.industry}
          </span>
          <span className="text-xs text-text-muted">
            {chainPositionLabel(indicators.chain_position)}
            {" · "}动态筛选 {relevantIds.size} 个关键指标
          </span>
        </div>
      )}

      {/* 估值概览 */}
      {valuation && <ValuationGrid valuation={valuation} />}

      {/* 最新财务指标（按行业过滤） */}
      {latest && (
        <FinancialMetricsDetail
          metrics={latest}
          relevantIds={relevantIds}
        />
      )}

      {/* 历史报告期对比 */}
      {financials && financials.length >= 2 && (
        <HistoricalTable periods={financials} />
      )}
    </div>
  );
}

/* ── 辅助函数 ── */

function chainPositionLabel(pos: string): string {
  const labels: Record<string, string> = {
    upstream: "上游 · 资源采掘",
    midstream: "中游 · 制造加工",
    downstream: "下游 · 品牌/消费",
    financial: "金融行业",
    other: "综合",
  };
  return labels[pos] ?? pos;
}

/* ── 估值比率四宫格 ── */

function ValuationGrid({ valuation }: { valuation: ValuationMetrics }) {
  const items = [
    { label: "市盈率 (PE)", value: valuation.pe, suffix: "", color: peColor(valuation.pe) },
    { label: "市净率 (PB)", value: valuation.pb, suffix: "", color: "" },
    { label: "市销率 (PS)", value: valuation.ps, suffix: "", color: "" },
    {
      label: "总市值",
      value: valuation.market_cap,
      suffix: "",
      color: "",
      formatter: formatYuanToYi,
    },
  ];

  return (
    <div>
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">估值概览</h4>
      <div className="grid grid-cols-4 gap-3">
        {items.map((item) => (
          <div
            key={item.label}
            className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50"
          >
            <div className="text-xs text-text-muted mb-1">{item.label}</div>
            <div className={`text-lg font-bold font-number ${item.color}`}>
              {item.formatter
                ? item.formatter(item.value)
                : item.value != null && item.value > 0
                  ? item.value.toFixed(2)
                  : "--"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function peColor(pe: number): string {
  if (pe <= 0) return "text-text-muted";
  if (pe > 50) return "text-accent-red";
  if (pe > 30) return "text-accent-gold";
  return "text-accent-green";
}

/* ── 财务指标详情（行业感知过滤） ── */

interface SectionItem {
  id: string;
  label: string;
  value: number;
  suffix: string;
  goodDir: "up" | "down";
}

interface Section {
  title: string;
  items: SectionItem[];
  cols?: number;
}

function FinancialMetricsDetail({
  metrics,
  relevantIds,
}: {
  metrics: FinancialMetrics;
  relevantIds: Set<string>;
}) {
  // 构建分类列表
  const allSections: Section[] = [
    {
      title: "盈利能力",
      items: [
        { id: "roe", label: "ROE", value: metrics.roe, suffix: "%", goodDir: "up" },
        { id: "roa", label: "ROA", value: metrics.roa, suffix: "%", goodDir: "up" },
        { id: "gross_margin", label: "毛利率", value: metrics.gross_margin, suffix: "%", goodDir: "up" },
        { id: "net_profit_margin", label: "净利率", value: metrics.net_profit_margin, suffix: "%", goodDir: "up" },
      ],
    },
    {
      title: "增长能力",
      items: [
        { id: "revenue_growth", label: "营收增长率", value: metrics.revenue_growth, suffix: "%", goodDir: "up" },
        { id: "net_profit_growth", label: "净利润增长率", value: metrics.net_profit_growth, suffix: "%", goodDir: "up" },
      ],
      cols: 2,
    },
    {
      title: "财务健康",
      items: [
        { id: "debt_ratio", label: "资产负债率", value: metrics.debt_ratio, suffix: "%", goodDir: "down" },
        { id: "current_ratio", label: "流动比率", value: metrics.current_ratio, suffix: "", goodDir: "up" },
        { id: "quick_ratio", label: "速动比率", value: metrics.quick_ratio, suffix: "", goodDir: "up" },
      ],
    },
    {
      title: "每股指标",
      items: [
        { id: "eps", label: "EPS", value: metrics.eps, suffix: "元", goodDir: "up" },
        { id: "book_value_per_share", label: "每股净资产", value: metrics.book_value_per_share, suffix: "元", goodDir: "up" },
        { id: "operating_cf_per_share", label: "每股经营性现金流", value: metrics.operating_cf_per_share, suffix: "元", goodDir: "up" },
      ],
    },
    {
      title: "运营效率",
      items: [
        { id: "inventory_turnover", label: "存货周转率", value: metrics.inventory_turnover, suffix: "次", goodDir: "up" },
        { id: "asset_turnover", label: "总资产周转率", value: metrics.asset_turnover, suffix: "次", goodDir: "up" },
      ],
      cols: 2,
    },
  ];

  // 按行业过滤：只显示 relevantIds 中的指标，隐藏不相关的
  const visibleSections = allSections
    .map((s) => ({
      ...s,
      items: s.items.filter((item) => relevantIds.has(item.id)),
    }))
    .filter((s) => s.items.length > 0);

  // 还没有行业数据时全量显示
  const sections = relevantIds.size > 0 ? visibleSections : allSections;

  return (
    <div className="space-y-4">
      {sections.map((section) => (
        <div key={section.title}>
          <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">
            {section.title}
          </h4>
          <div className={`grid grid-cols-${section.cols ?? 3} gap-3`}>
            {section.items.map((item) => (
              <div
                key={item.id}
                className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50"
              >
                <div className="flex justify-between items-baseline">
                  <span className="text-xs text-text-muted">{item.label}</span>
                  <span className={`font-number text-sm font-medium ${metricColor(item)}`}>
                    {formatMetric(item)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function metricColor(item: SectionItem): string {
  if (item.value <= 0) return "text-text-muted";
  return item.goodDir === "up" ? "text-accent-green" : "text-accent-gold";
}

function formatMetric(item: SectionItem): string {
  if (item.value <= 0) return "--";
  const val = item.value.toFixed(2);
  return `${val}${item.suffix}`;
}

/* ── 历史报告期对比表 ── */

function HistoricalTable({ periods }: { periods: FinancialMetrics[] }) {
  const columns = [
    { key: "report_date" as const, label: "报告期", format: (v: string) => v.slice(0, 7) },
    { key: "roe" as const, label: "ROE(%)", format: (v: number) => v.toFixed(1) },
    { key: "eps" as const, label: "EPS", format: (v: number) => v.toFixed(2) },
    { key: "gross_margin" as const, label: "毛利率(%)", format: (v: number) => v.toFixed(1) },
    { key: "net_profit_margin" as const, label: "净利率(%)", format: (v: number) => v.toFixed(1) },
    { key: "debt_ratio" as const, label: "负债率(%)", format: (v: number) => v.toFixed(1) },
    { key: "revenue_growth" as const, label: "营收增长(%)", format: (v: number) => v.toFixed(1) },
    { key: "net_profit_growth" as const, label: "净利润增长(%)", format: (v: number) => v.toFixed(1) },
  ] as const;

  return (
    <div>
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">历史对比</h4>
      <div className="overflow-x-auto rounded-lg border border-bg-tertiary">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-bg-tertiary/50">
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 text-left text-text-muted font-medium whitespace-nowrap">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.slice(0, 8).map((period, idx) => (
              <tr
                key={period.report_date || idx}
                className="border-t border-bg-tertiary hover:bg-bg-tertiary/30 transition-colors"
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2 font-number text-text-primary whitespace-nowrap">
                    {col.format(period[col.key] as never)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── 格式化工具 ── */

function formatYuanToYi(value: number): string {
  if (value <= 0) return "--";
  const yi = value / 1_0000_0000;
  if (yi >= 10000) {
    return `${(yi / 10000).toFixed(2)}万亿`;
  }
  return `${yi.toFixed(1)}亿`;
}
