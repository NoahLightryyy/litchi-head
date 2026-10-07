"use client";

import type { StockQuote } from "@/lib/types/stock";
import { formatPrice, formatChangePct } from "@/lib/utils";
import { formatQuoteOptionalNumber, formatQuoteTime } from "@/lib/quote-display";

interface QuoteCardProps {
  quote: StockQuote | null;
  loading?: boolean;
}

/** 实时行情卡片：价格 + 涨跌幅 + 关键指标 */
export function QuoteCard({ quote, loading }: QuoteCardProps) {
  if (loading || !quote) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 animate-pulse">
        <div className="h-5 w-20 bg-bg-tertiary rounded mb-3" />
        <div className="h-10 w-32 bg-bg-tertiary rounded mb-3" />
        <div className="h-3 w-full bg-bg-tertiary rounded" />
      </div>
    );
  }

  const isUp = quote.change_pct >= 0;

  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
      {/* 价格区 */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-text-primary">{quote.name}</h1>
          <span className="text-xs text-text-muted bg-bg-tertiary px-2 py-0.5 rounded">
            {quote.code}
          </span>
        </div>
      </div>

      <div className="flex items-baseline gap-4">
        <span className="text-4xl font-number font-bold text-text-primary">
          {formatPrice(quote.price)}
        </span>
        <div className="flex items-center gap-1">
          <span className={`font-number text-lg ${isUp ? "text-accent-green" : "text-accent-red"}`}>
            {isUp ? "▲ +" : "▼ "}{quote.change.toFixed(2)}
          </span>
          <span className={`font-number text-lg ${isUp ? "text-accent-green" : "text-accent-red"}`}>
            ({formatChangePct(quote.change_pct)})
          </span>
        </div>
      </div>

      {/* 指标网格 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-4 mt-5 pt-4 border-t border-bg-tertiary">
        <StatItem label="今开" value={formatPrice(quote.open)} />
        <StatItem label="最高" value={formatPrice(quote.high)} color="text-accent-green" />
        <StatItem label="最低" value={formatPrice(quote.low)} color="text-accent-red" />
        <StatItem label="昨收" value={formatPrice(quote.prev_close)} />
        <StatItem label="成交量" value={`${(quote.volume / 10000).toFixed(1)}万`} />
        <StatItem label="换手率" value={formatQuoteOptionalNumber(quote.turnover_rate, 2, "%")} />
        <StatItem label="主力流入" value={formatQuoteOptionalNumber(quote.fund_flow, 1, "亿", true)} color="text-accent-green" />
        <StatItem label="成交额" value={`${(quote.amount / 10000_0000).toFixed(1)}亿`} />
      </div>

      {/* 数据新鲜度 */}
      <p className="mt-3 text-xs text-text-muted">
        {quote.source === "sina" ? "新浪" : quote.source === "eastmoney" ? "东方财富" : "行情来源"}
        {quote.verification_status === "single_source" ? " · 单源报价，未交叉验证" : ""}
        {quote.fetched_at ? ` · 报价时间 ${formatQuoteTime(quote.fetched_at)}（北京时间）` : ""}
      </p>
    </div>
  );
}

function StatItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`font-number text-sm ${color || "text-text-primary"}`}>{value}</div>
    </div>
  );
}
