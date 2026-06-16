"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { TrendingUp, DollarSign, MessageSquare, ShieldCheck } from "lucide-react";
import { useStockQuote, useStockNews } from "@/lib/hooks/use-stock";
import { QuoteCard } from "@/components/stock/quote-card";
import { KlineChart } from "@/components/stock/kline-chart";
import { DebatePanel } from "@/components/stock/debate-panel";
import { NewsFeed } from "@/components/stock/news-feed";

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
  const { data: quote, isLoading: quoteLoading } = useStockQuote(code);
  const { data: news, isLoading: newsLoading } = useStockNews(code);

  const stockName = quote?.name ?? code;

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {/* 面包屑 */}
      <div className="flex items-center gap-2 text-sm">
        <a href="/" className="text-text-secondary hover:text-text-primary transition-colors">
          宏观总览
        </a>
        <span className="text-text-muted">/</span>
        <a href={`/sector/000000`} className="text-text-secondary hover:text-text-primary transition-colors">
          板块
        </a>
        <span className="text-text-muted">/</span>
        <span className="text-text-primary font-medium">{stockName}</span>
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

      {/* Tab 内容 */}
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 min-h-64">
        {activeTab === "technical" && (
          <div className="text-sm text-text-muted text-center py-8">
            技术指标面板（待实现：MA/RSI/MACD/布林带详情）
          </div>
        )}
        {activeTab === "capital" && (
          <div className="text-sm text-text-muted text-center py-8">
            资金流向面板（待实现：主力净流入趋势/大单追踪）
          </div>
        )}
        {activeTab === "debate" && (
          <DebatePanel stockCode={code} stockName={stockName} />
        )}
        {activeTab === "trust" && (
          <div className="text-sm text-text-muted text-center py-8">
            信任度看板（待实现：大师历史准确率/校准曲线）
          </div>
        )}
      </div>

      {/* 新闻 */}
      <NewsFeed items={news ?? []} loading={newsLoading} code={code} />
    </div>
  );
}
