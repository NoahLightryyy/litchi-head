"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { TrendingUp, DollarSign, MessageSquare, ShieldCheck, BarChart3 } from "lucide-react";
import { useStockQuote, useStockNews } from "@/lib/hooks/use-stock";
import { QuoteCard } from "@/components/stock/quote-card";
import { DebatePanel } from "@/components/stock/debate-panel";
import { NewsFeed } from "@/components/stock/news-feed";
import { CapitalFlowPanel } from "@/components/stock/capital-flow-panel";
import { TechnicalIndicatorsPanel } from "@/components/stock/technical-indicators-panel";
import { FinancialPanel } from "@/components/stock/financial-panel";
import { TrustChart } from "@/components/stock/trust-chart";
import { IntradayBattlefieldPanel } from "@/components/stock/intraday-battlefield-panel";
import { useTrustLeaderboard } from "@/lib/hooks/use-debate";

const TABS = [
  { id: "technical", label: "技术分析", icon: TrendingUp },
  { id: "capital", label: "资金流向", icon: DollarSign },
  { id: "financial", label: "财务分析", icon: BarChart3 },
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
  const { data: quote, isLoading: quoteLoading, isError: quoteError, refetch: refreshQuote, isFetching: quoteFetching } = useStockQuote(code);
  const { data: news, isLoading: newsLoading, isError: newsError, refetch: refreshNews, isFetching: newsFetching } = useStockNews(code);
  const { data: trustReports, isLoading: trustLoading } = useTrustLeaderboard();

  const stockName = quote?.name ?? code;


  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {/* 面包屑 */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/" className="text-text-secondary hover:text-text-primary transition-colors">
          市场总览
        </Link>
        <span className="text-text-muted">/</span>
        <span className="text-text-muted">个股</span>
        <span className="text-text-muted">/</span>
        <span className="text-text-primary font-medium">{stockName}</span>
        <span className="text-xs text-text-muted">({code})</span>
      </div>

      {/* 行情卡片 */}
      {!quoteLoading && (quoteError || !quote) ? <div role="status" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
        <p>个股名称与报价尚未取得（{code}）</p>
        <p className="mt-2 text-sm text-text-muted">当前报价接口未提供有效数据。分时、K线等模块独立加载；不把未知报价填成零。</p>
        <button disabled={quoteFetching} onClick={() => void refreshQuote()} className="mt-3 text-sm text-accent-blue">{quoteFetching ? "正在获取…" : "重新获取报价"}</button>
      </div> : <QuoteCard quote={quote ?? null} loading={quoteLoading} />}

      {/* 真实盘中分钟结构与数据来源状态 */}
      <IntradayBattlefieldPanel key={code} code={code} />


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
        {activeTab === "financial" && (
          <FinancialPanel key={`fin-${code}`} code={code} />
        )}
        {activeTab === "debate" && (
          <DebatePanel stockCode={code} stockName={stockName} />
        )}
        {activeTab === "trust" && (
          <TrustChart reports={trustReports ?? []} loading={trustLoading} />
        )}
      </div>

      {/* 新闻 */}
      {newsError ? <div role="alert" className="rounded-lg border border-bg-tertiary p-5">关联新闻请求失败</div> : <NewsFeed items={news ?? []} loading={newsLoading} />}
      {!newsLoading && (newsError || !news?.length) && <button disabled={newsFetching} onClick={() => void refreshNews()} className="self-start text-sm text-accent-blue">{newsFetching ? "正在获取…" : "重新获取关联新闻"}</button>}
    </div>
  );
}
