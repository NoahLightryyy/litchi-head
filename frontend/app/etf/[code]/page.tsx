"use client";

import { ResearchContext } from "@/components/research/research-context";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseEtfDetail } from "@/lib/etf-display";

const time = (value: string) => new Date(value).toLocaleString("zh-CN", {timeZone:"Asia/Shanghai",hour12:false});
const price = (value: number | null) => value === null ? "—" : value.toFixed(3);

export default function EtfPage() {
  const {code} = useParams<{code:string}>();
  const valid = /^\d{6}$/.test(code);
  const query = useQuery({queryKey:["etf",code],enabled:valid,retry:false,staleTime:30000,
    queryFn:async ({signal}) => parseEtfDetail(await api.getRaw<unknown>(`/etfs/${code}`,undefined,{signal}),code)});
  const data = query.data, quote = data?.quote;
  return <div className="mx-auto max-w-5xl space-y-6">
    <Link href="/search" className="text-sm text-accent-blue">← 搜索与发现</Link>
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="mb-1 text-xs text-accent-blue">场内 ETF</p><h1 className="text-2xl font-semibold">{data?.identity.name ?? "ETF资料与行情"}</h1>
        <p className="mt-2 text-sm text-text-muted">{code}{data ? ` · ${data.identity.exchange === "SH" ? "上海" : "深圳"}证券交易所` : ""}</p></div>
      <button disabled={!valid || query.isFetching} onClick={()=>void query.refetch()} className="rounded-lg border border-bg-tertiary px-4 py-2 text-sm text-accent-blue disabled:opacity-50">{query.isFetching ? "正在读取…" : "刷新行情"}</button>
    </div>
    {!valid ? <p role="alert">ETF代码格式无效</p> : query.isPending ? <p role="status" className="rounded-lg bg-bg-secondary p-6">正在读取ETF身份与行情…</p> : null}
    {query.isError && <p role="alert" className="rounded-lg bg-accent-red/10 p-4 text-accent-red">{query.error.message}{data ? "；以下保留上次成功取得的数据，请留意时间。" : ""}</p>}
    {valid && <ResearchContext key={code} kind="etf" code={code} name={data?.identity.name ?? code} />}
    {data && <>
      <section className="rounded-xl border border-bg-tertiary bg-bg-secondary p-5 space-y-5">
        <div><h2 className="text-sm text-text-muted">场内交易价格 / 元</h2>
          <p className="mt-2 text-4xl font-number">{quote ? price(quote.price) : "—"}</p>
          {quote && <p className={`mt-2 font-number ${quote.change>=0 ? "text-stock-up" : "text-stock-down"}`}>{quote.change>0 ? "+" : ""}{quote.change.toFixed(3)}（{quote.change_pct>0 ? "+" : ""}{quote.change_pct.toFixed(2)}%）</p>}
        </div>
        {quote ? <>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">{[["前收",quote.previous_close],["今开",quote.open],["最高",quote.high],["最低",quote.low]].map(([label,value])=><div key={String(label)}><dt className="text-xs text-text-muted">{label}</dt><dd className="mt-1 font-number">{price(value as number|null)}</dd></div>)}</dl>
          <p className="text-xs text-text-muted">报价时间：{time(quote.quoted_at)}（北京时间） · 行情简称：{quote.source_name}</p>
        </> : <p role="status" className="text-sm text-text-muted">暂无可核验报价</p>}
        {data.limitations.map(item=><p key={item} className="text-sm leading-6 text-text-muted">{item}</p>)}
      </section>
      <section className="rounded-xl border border-bg-tertiary bg-bg-secondary p-5 space-y-3">
        <h2 className="font-semibold">基金身份与来源</h2>
        <p className="text-sm">{data.identity.name} · {data.identity.symbol} · ETF</p>
        <p className="text-sm text-text-muted">基金身份来自新浪ETF分类目录。报价日期可能早于当前日期，请结合报价时间查看。</p>
        <p className="text-xs text-text-muted">目录采集：{time(data.catalog_fetched_at)}（北京时间）</p>
        <a href={data.source_url} target="_blank" rel="noopener noreferrer" className="inline-block text-sm text-accent-blue underline">查看新浪ETF目录 ↗</a>
      </section>
    </>}
  </div>;
}
