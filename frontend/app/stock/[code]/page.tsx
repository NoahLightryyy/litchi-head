"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { TrendingUp, DollarSign, MessageSquare, ShieldCheck } from "lucide-react";
import { useStockQuote, useStockNews } from "@/lib/hooks/use-stock";
import { QuoteCard } from "@/components/stock/quote-card";
import { KlineChart } from "@/components/stock/kline-chart";
import { DebatePanel } from "@/components/stock/debate-panel";
import { NewsFeed } from "@/components/stock/news-feed";
import { CapitalFlowPanel } from "@/components/stock/capital-flow-panel";
import { TechnicalIndicatorsPanel } from "@/components/stock/technical-indicators-panel";
import { TrustChart } from "@/components/stock/trust-chart";
import { useTrustLeaderboard } from "@/lib/hooks/use-debate";

const TABS = [
  { id: "technical", label: "技术分析", icon: TrendingUp },
  { id: "capital", label: "资金流向", icon: DollarSign },
  { id: "debate", label: "AI 辩论", icon: MessageSquare },
  { id: "trust", label: "信任度", icon: ShieldCheck },
] as const;

type TabId = (typeof TABS)[number]["id"];

/** 个股决策页 */
export default function StockPage() {
  const params = useParams();
  const code = params.code as string;
  const [activeTab, setActiveTab] = useState<TabId>("debate");

  // ── 数据 ──
  const { data: quote, isLoading: quoteLoading, isError: quoteError } = useStockQuote(code);
  const { data: news, isLoading: newsLoading } = useStockNews(code);
  const { data: trustReports, isLoading: trustLoading } = useTrustLeaderboard();

  const stockName = quote?.name ?? code;

  // ── 错误态 ──
  if (quoteError && !quoteLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2 text-sm">
          <a href="/" className="text-text-secondary hover:text-text-primary transition-colors">
            宏观总览
          </a>
          <span className="text-text-muted">/</span>
          <span className="text-text-muted">{code}</span>
        </div>
        <div className="p-8 rounded-lg border border-bg-tertiary bg-bg-secondary text-center">
          <div className="text-4xl mb-4">📡</div>
          <p className="text-sm text-text-muted mb-2">个股数据加载失败</p>
          <p className="text-xs text-text-muted mb-4">股票代码 {code} 数据暂时不可用</p>
          <div className="flex items-center justify-center gap-3">
            <a href="/" className="px-4 py-2 rounded-md bg-bg-tertiary text-text-secondary text-sm font-medium hover:bg-bg-elevated transition-colors">
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
        <span className="text-text-muted">个股</span>
        <span className="text-text-muted">/</span>
        <span className="text-text-primary font-medium">{stockName}</span>
        <span className="text-xs text-text-muted">({code})</span>
      </div>

      {/* 行情卡片 */}
      <QuoteCard quote={quote ?? null} loading={quoteLoading} />

      {/* K 线图 */}
      <KlineChart code={code} />

      {/* Tab 切换 */}
      <div className="flex gap-1 border-b border-bg-tertiary">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-accent-blue text-accent-blue"
                  : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab 内容（带淡入过渡） */}
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 min-h-64 transition-opacity duration-200">
        {activeTab === "technical" && (
          <TechnicalIndicatorsPanel key={`tech-${code}`} code={code} />
        )}
        {activeTab === "capital" && (
          <CapitalFlowPanel key={`cap-${code}`} code={code} />
        )}
        {activeTab === "debate" && (
          <DebatePanel stockCode={code} stockName={stockName} />
        )}
        {activeTab === "trust" && (
          <TrustChart reports={trustReports ?? []} loading={trustLoading} />
        )}
      </div>

      {/* 新闻 */}
      <NewsFeed items={news ?? []} loading={newsLoading} code={code} />
    </div>
  );
}
