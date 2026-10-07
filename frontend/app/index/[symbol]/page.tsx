"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { indexNames, parseIndexHistory } from "@/lib/index-history";
import { aggregateRawPeriod, periodLabels, type DisplayPeriod } from "@/lib/raw-period";
import { CandlestickChart } from "@/components/stock/candlestick-chart";

export default function IndexPage() {
  const {symbol} = useParams<{symbol:string}>();
  const [period,setPeriod] = useState<DisplayPeriod>("daily");
  const query = useQuery({queryKey:["index-history",symbol],enabled:!!indexNames[symbol],retry:false,staleTime:300000,
    queryFn:async ({signal})=>parseIndexHistory(await api.getRaw(`/market/indices/${symbol}/history`,undefined,{signal}),symbol)});
  return <div className="space-y-5">
    <Link href="/" className="text-accent-blue">← 市场总览</Link>
    <h1 className="text-xl font-semibold">{indexNames[symbol] ?? "未知指数"} <span className="text-sm text-text-muted">{symbol}</span></h1>
    {indexNames[symbol] && <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-4">
      <div className="flex flex-wrap gap-2 items-center"><h2 className="mr-auto font-semibold">指数 K 线</h2>
        {(Object.keys(periodLabels) as DisplayPeriod[]).map(p=><button key={p} aria-pressed={period===p} onClick={()=>setPeriod(p)} className={`rounded px-3 py-1 ${period===p?"bg-accent-blue text-white":"bg-bg-tertiary"}`}>{periodLabels[p]}</button>)}
        <button disabled={query.isFetching} onClick={()=>void query.refetch()} className="text-accent-blue">刷新</button>
      </div>
      <p className="text-xs text-text-muted">腾讯 · 单源未交叉验证 · 指数点位；成交量保留来源原始单位，未换算为股或手。</p>
      {query.isPending ? <p role="status">正在加载指数历史…</p> : query.isError ? <p role="alert">指数历史加载失败，请点击刷新重试。</p> : query.data ? <>
        <p className="text-xs text-text-muted">{query.data.bars[0].date} — {query.data.bars.at(-1)?.date} · {query.data.bars.length} 根日线（本次最多取得640根，并非全部历史）</p>
        <p className="text-xs text-text-muted">读取时间：{new Date(query.data.fetched_at).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai"})} 北京时间。可含当日未结束日线；周/月线按这批日线聚合，首尾周期可能不完整。</p>
        <CandlestickChart data={aggregateRawPeriod(query.data.bars,period)} priceUnit="点" volumeLabel="成交量（来源原始单位）" />
      </> : <p>暂无指数历史数据。</p>}
    </section>}
  </div>;
}
