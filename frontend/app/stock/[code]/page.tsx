"use client";

import { ResearchContext } from "@/components/research/research-context";

import { useLocale } from "@/components/shared/locale-provider";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { TrendingUp, DollarSign, MessageSquare, ShieldCheck, BarChart3 } from "lucide-react";
import { useStockIdentity, useStockQuote } from "@/lib/hooks/use-stock";
import { stockDisplayName } from "@/lib/stock-identity";
import { QuoteCard } from "@/components/stock/quote-card";
import { WatchButton } from "@/components/stock/watch-button";
import { CompanyResearchPanel } from "@/components/stock/company-research-panel";
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
  { id: "debate", label: "流派分析", icon: MessageSquare },
  { id: "trust", label: "信任度", icon: ShieldCheck },
] as const;

type TabId = (typeof TABS)[number]["id"];

/** 个股决策页 */
export default function StockPage() {
  const { t } = useLocale();
  const params = useParams();
  const code = params.code as string;
  const [activeTab, setActiveTab] = useState<TabId>("debate");

  // ── 数据 ──
  const { data: rawQuote, isLoading: quoteLoading, isError: quoteError, refetch: refreshQuote, isFetching: quoteFetching } = useStockQuote(code);
  const { data: trustReports, isLoading: trustLoading } = useTrustLeaderboard();

  const { data: identity } = useStockIdentity(code);
  const quote = rawQuote?.code === code ? rawQuote : null;
  const stockName = stockDisplayName(code, quote, identity);
  const retryQuote = <button disabled={quoteFetching} onClick={() => void refreshQuote()} className="mt-3 text-sm text-accent-blue disabled:opacity-50">{quoteFetching ? t("正在获取…") : t("重新获取报价")}</button>;


  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {/* 面包屑 */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/" className="text-text-secondary hover:text-text-primary transition-colors">
          {t("市场总览")}
        </Link>
        <span className="text-text-muted">/</span>
        <span className="text-text-muted">{t("个股")}</span>
        <span className="text-text-muted">/</span>
        <span className="text-text-primary font-medium">{stockName}</span>
        <span className="text-xs text-text-muted">({code})</span>
      </div>

      {/* 行情卡片 */}
      <WatchButton code={code} name={stockName} />
      {quote ? <>
        <QuoteCard quote={quote} />
        {quoteError && <div role="status" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 text-sm">
          <p>{t("刷新未成功，先显示上次报价，请留意报价时间。")}</p>
          {retryQuote}
        </div>}
      </> : quoteLoading ? <QuoteCard quote={null} loading /> : <div role="status" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
        <p>{stockName === code ? code : `${stockName}（${code}）`} · {t("报价暂未取得")}</p>
        <p className="mt-2 text-sm text-text-muted">{t("报价来源暂时不可用，可稍后重试。公司资料和K线仍可单独查看。")}</p>
        {retryQuote}
      </div>}

      <ResearchContext key={`research-${code}`} kind="stock" code={code} name={stockName} />

      <CompanyResearchPanel key={`company-${code}`} code={code} />

      {/* 真实盘中分钟结构与数据来源状态 */}
      <IntradayBattlefieldPanel key={`intraday-${code}`} code={code} />


      {/* Tab 切换 */}
      <div className="flex gap-1 overflow-x-auto border-b border-bg-tertiary">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex shrink-0 items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-accent-blue text-accent-blue"
                  : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t(tab.label)}
            </button>
          );
        })}
      </div>

      {/* Tab 内容（带淡入过渡） */}
      <div id="research" className="scroll-mt-24 rounded-lg border border-bg-tertiary bg-bg-secondary p-5 min-h-64 transition-opacity duration-200">
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
      <NewsFeed key={`news-${code}`} code={code} />
    </div>
  );
}
