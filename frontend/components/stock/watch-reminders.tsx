"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { checkedWatchQuote, planReminder, priceReminder, readWatchResearch, type WatchResearch } from "@/lib/watchlist-reminders";
import type { StockQuote } from "@/lib/types/stock";

const stamp = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
const horizonName = { short: "这几天", medium: "接下来几个月", long: "长期持有" };
const requestSignal = (signal: AbortSignal) => AbortSignal.any([signal, AbortSignal.timeout(20_000)]);

export function WatchReminders({ code }: { code: string }) {
  const quote = useQuery({ queryKey: ["watchlist", "quote", code],
    queryFn: async ({ signal }) => checkedWatchQuote(await api.get<unknown>(`/stocks/${code}/quote`, undefined, { signal: requestSignal(signal) }), code),
    retry: false, staleTime: 30_000, refetchInterval: 60_000, refetchIntervalInBackground: false });
  const research = useQuery({ queryKey: ["watchlist", "research", code],
    queryFn: ({ signal }) => readWatchResearch(code, requestSignal(signal)), retry: false, staleTime: 60_000 });
  return <WatchReminderContent code={code} quote={quote.data} research={research.data}
    quoteLoading={quote.isFetching} researchLoading={research.isFetching}
    quoteError={quote.isError} researchError={research.isError}
    offline={quote.fetchStatus === "paused" || research.fetchStatus === "paused"}
    onRefresh={() => { void quote.refetch(); void research.refetch(); }} />;
}

export function WatchReminderContent({ code, quote, research, quoteLoading, researchLoading, quoteError, researchError, offline, onRefresh }: {
  code: string; quote?: StockQuote | null; research?: WatchResearch; quoteLoading: boolean; researchLoading: boolean;
  quoteError: boolean; researchError: boolean; offline: boolean; onRefresh: () => void;
}) {
  const movement = quote ? priceReminder(quote) : null;
  const plan = research?.plan;
  return <section aria-label="这只股票要留意什么" className="space-y-3">
    <div className="flex flex-wrap justify-between gap-2">
      <h3 className="font-medium">现在要留意什么</h3>
      <button onClick={onRefresh} disabled={quoteLoading || researchLoading || offline} className="text-sm text-accent-blue disabled:opacity-50">
        {quoteLoading || researchLoading ? "正在查看…" : "刷新提醒"}
      </button>
    </div>
    {offline && <p role="status" className="text-sm text-text-muted">网络断了，已有内容仍可看；联网后再刷新。</p>}
    {quote && movement && <div className="rounded-md bg-bg-primary p-3">
      <div className="flex flex-wrap items-baseline gap-3"><strong className="font-number text-xl">¥{quote.price.toFixed(2)}</strong><span className="text-sm">{movement.title}</span></div>
      <p className="mt-1 text-sm">{movement.detail}</p>
      <p className="mt-2 text-xs text-text-muted">最近报价：{quote.fetched_at ? `${stamp(quote.fetched_at)}（北京时间）` : "时间未提供，先核对再用"} · {quote.source === "sina" ? "新浪" : quote.source === "eastmoney" ? "东方财富" : "行情来源"}</p>
    </div>}
    {quoteError && <p role="status" className="text-sm text-accent-gold">这次没拿到新报价。{quote ? "上面保留的是之前的价格，请看报价时间。" : "暂时看不出价格变化，可以稍后刷新。"}</p>}
    {!quote && !quoteError && <p role="status" className="text-sm text-text-muted">{quoteLoading ? "正在查看价格变化…" : "暂时没有报价，先看看已有分析。"}</p>}
    {research?.latestStatus === "failed" && <p className="text-sm text-accent-gold">最近一次分析没完成，{plan ? "下面保留上次的提醒。" : "可进入详情重新分析。"}</p>}
    {(research?.latestStatus === "running" || research?.latestStatus === "queued") && <p role="status" className="text-sm text-text-muted">新的分析还在整理，{plan ? "下面是上次的提醒。" : "完成后刷新这里查看。"}</p>}
    {researchError && <p role="status" className="text-sm text-accent-gold">这次没读到新的分析提醒，{plan ? "下面保留上次内容。" : "不代表没有风险。稍后刷新或进入详情查看。"}</p>}
    {plan ? <>
      <p className="text-sm text-text-muted">上次分析的买入提醒 · {stamp(plan.generated_at)}（北京时间）<span className="block text-xs">这些条件还没有按此刻行情重新检查，不能当成刚刚出现的信号。</span></p>
      <div className="grid gap-2 md:grid-cols-3">
        {plan.plans.map(item => { const reminder = planReminder(item); return <div key={item.horizon} className="rounded-md border border-bg-tertiary p-3">
          <p className="text-xs text-text-muted">{horizonName[item.horizon]}</p>
          <h4 className="mt-1 font-semibold">{reminder.title}</h4>
          <p className="mt-2 text-sm">{reminder.detail}</p>
          <details className="mt-2 text-sm"><summary className="cursor-pointer text-accent-blue">具体等什么、什么情况要小心</summary>
            <p className="mt-2">{item.summary}</p>
            <ul className="mt-2 list-disc space-y-1 pl-4">{item.conditions.map((condition, index) => <li key={index}>{condition.status === "met" ? "当时已出现" : condition.status === "unmet" ? "当时还没出现" : "还没看清"}：{condition.condition}</li>)}</ul>
            <p className="mt-2 font-medium">出现这些变化，要重新考虑：</p>
            <ul className="list-disc space-y-1 pl-4">{item.invalidation.map((text, index) => <li key={index}>{text}</li>)}</ul>
          </details>
        </div>; })}
      </div>
    </> : !researchError && <div className="text-sm">
      <p>{researchLoading ? "正在找已有的买入提醒…" : "还没有这只股票的买入提醒。打开详情，点“帮我看看机会和风险”，不用自己写问题。"}</p>
    </div>}
    <Link className="inline-block rounded border border-accent-blue px-3 py-2 text-sm text-accent-blue" href={`/stock/${code}#research`}>看看机会和风险 →</Link>
  </section>;
}
