"use client";

import {useState} from "react";
import Link from "next/link";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useDebounce} from "@/lib/hooks/use-debounce";

type Hit = {code:string; name:string; kind:"stock"|"industry"|"concept"};
type Results = {data:Hit[]; total:number; failed_sources:string[]};
type Gainer = {code:string;name:string;price:number;change_pct:number;quoted_at:string};
type Gainers = {data:Gainer[];scope:string;fetched_at:string;cached:boolean;failed_count:number;error:boolean};
const labels = {stock:"个股",industry:"行业板块",concept:"概念板块"};

export function StockDiscovery({showGainers=false}:{showGainers?:boolean}) {
  const [query,setQuery]=useState("");
  const keyword=useDebounce(query.trim(),300);
  const results=useQuery({queryKey:["discovery","search",keyword],queryFn:()=>api.getRaw<Results>(`/discovery/search?q=${encodeURIComponent(keyword)}`),enabled:!!keyword,retry:false,staleTime:60000});
  return <div className="space-y-4">
    <label className="block text-sm text-text-secondary">搜索股票或板块
      <input maxLength={80} aria-label="搜索股票或板块" value={query} onChange={event=>setQuery(event.target.value)} placeholder="输入代码、公司名称或板块，例如：半导体"
        className="mt-2 w-full rounded-lg border border-bg-tertiary bg-bg-secondary px-4 py-3 text-text-primary focus:outline-accent-blue"/>
    </label>
    {!!query.trim() && <section aria-live="polite" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      {query.trim()!==keyword || results.isLoading ? <p>正在搜索…</p> : results.isError ? <div role="alert">搜索暂时失败。<button onClick={()=>void results.refetch()} className="ml-2 text-accent-blue">重试</button></div> : results.data && <>
        {!!results.data.failed_sources.length && <p role="status" className="mb-2 text-accent-gold">暂未取得：{results.data.failed_sources.join("、")}，当前结果可能不完整。</p>}
        <p className="mb-2 text-xs text-text-muted">{results.data.total ? `找到 ${results.data.total} 项，显示前 ${results.data.data.length} 项` : "未找到匹配结果，可尝试股票代码、公司名称或板块名称。"}</p>
        <div className="max-h-80 overflow-y-auto divide-y divide-bg-tertiary">{results.data.data.map(hit=><Link key={`${hit.kind}:${hit.code}`} href={hit.kind==="stock"?`/stock/${hit.code}`:`/sector/${hit.code}`} className="flex flex-wrap justify-between gap-2 py-3 text-sm hover:text-accent-blue"><span>{hit.name} <span className="text-text-muted">{hit.code}</span></span><span>{labels[hit.kind]}</span></Link>)}</div>
      </>}
    </section>}
    {showGainers && <GainerList/>}
  </div>;
}

function GainerList(){
  const result=useQuery({queryKey:["discovery","gainers"],queryFn:()=>api.getRaw<Gainers>("/discovery/gainers"),retry:false,staleTime:120000});
  return <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
    <div className="flex justify-between gap-3"><h2 className="font-semibold">涨幅靠前个股</h2><button disabled={result.isFetching} onClick={()=>void result.refetch()} className="text-sm text-accent-blue">{result.isFetching?"更新中…":"刷新榜单"}</button></div>
    <p className="mt-2 text-xs text-text-muted">按来源涨幅排序，供发现股票；涨幅不代表关注热度或投资价值。新股的参考价格口径可能不同。</p>
    {result.isLoading ? <p className="py-6">正在读取榜单和报价时间…</p> : result.isError ? <p role="alert" className="py-6">榜单暂时不可用，请重试。</p> : result.data && <>
      <p className="mt-2 text-xs text-text-muted">{result.data.scope}。单源未交叉验证；休市时保留最后报价，请查看每行时间。</p>
      {(result.data.error || result.data.failed_count>0) && <p role="status" className="mt-2 text-accent-gold">{result.data.error?"更新未完成，当前仅展示已有数据。":"部分候选报价未取得，榜单不完整。"}</p>}
      {!result.data.data.length ? <p className="py-6">暂无可展示的报价。</p>:<div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="text-text-muted"><th className="p-2">个股</th><th>价格</th><th>来源涨幅</th><th>报价时间（北京时间）</th></tr></thead><tbody>{result.data.data.map(item=><tr key={item.code} className="border-t border-bg-tertiary"><td className="p-2"><Link className="text-accent-blue" href={`/stock/${item.code}`}>{item.name}<span className="block text-xs text-text-muted">{item.code}</span></Link></td><td>{item.price.toFixed(2)}</td><td className={item.change_pct>=0?"text-stock-up":"text-stock-down"}>{item.change_pct>0?"+":""}{item.change_pct.toFixed(2)}%</td><td>{new Date(item.quoted_at).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false})}</td></tr>)}</tbody></table></div>}
    </>}
  </section>;
}
