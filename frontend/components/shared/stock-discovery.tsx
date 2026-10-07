"use client";

import {useState, useMemo, useSyncExternalStore} from "react";
import Link from "next/link";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useDebounce} from "@/lib/hooks/use-debounce";

import {addSearchHistory, parseSearchHistory, saveSearchHistory, searchHistorySnapshot, subscribeSearchHistory} from "@/lib/search-history";

type Hit = {code:string; name:string; kind:"stock"|"industry"|"concept"};
type Results = {data:Hit[]; total:number; failed_sources:string[]};

import {DiscoveryRankings} from "@/components/shared/discovery-rankings";

const labels = {stock:"个股",industry:"行业板块",concept:"概念板块"};

export function StockDiscovery({showGainers=false}:{showGainers?:boolean}) {
  const [query,setQuery]=useState("");
  const historyRaw = useSyncExternalStore(subscribeSearchHistory, searchHistorySnapshot, () => "[]");
  const history = useMemo(() => parseSearchHistory(historyRaw), [historyRaw]);
  const remember = (value: string) => {
    if (value.trim()) saveSearchHistory(addSearchHistory(parseSearchHistory(searchHistorySnapshot()), value));
  };
  const keyword=useDebounce(query.trim(),300);
  const results=useQuery({queryKey:["discovery","search",keyword],queryFn:()=>api.getRaw<Results>(`/discovery/search?q=${encodeURIComponent(keyword)}`),enabled:!!keyword,retry:false,staleTime:60000});
  return <div className="space-y-4">
    <form onSubmit={event => { event.preventDefault(); remember(query); }} className="flex items-end gap-2">
    <label className="block flex-1 text-sm text-text-secondary">搜索股票或板块
      <input maxLength={80} aria-label="搜索股票或板块" value={query} onChange={event=>setQuery(event.target.value)} placeholder="输入代码、公司名称或板块，例如：半导体"
        className="mt-2 w-full rounded-lg border border-bg-tertiary bg-bg-secondary px-4 py-3 text-text-primary focus:outline-accent-blue"/>
    </label>
    <button type="submit" disabled={!query.trim()} className="rounded-lg bg-accent-blue px-4 py-3 text-sm text-white disabled:opacity-50">搜索</button>
    </form>
    <section aria-label="搜索历史" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      <div className="flex items-center justify-between"><h2 className="text-sm font-medium">搜索历史</h2>
        {history.length > 0 && <button onClick={() => saveSearchHistory([])} className="text-xs text-text-muted hover:text-accent-blue">清空历史</button>}
      </div>
      <p className="mt-1 text-xs text-text-muted">保留最近20条；按回车、点击搜索或打开结果时记录。仅存于此浏览器，禁用存储时仅当前页面有效。</p>
      {!history.length ? <p className="mt-3 text-sm text-text-muted">暂无搜索记录</p> : <ul className="mt-3 flex flex-wrap gap-2">
        {history.map(item => <li key={item.toLocaleLowerCase()} className="flex rounded-md border border-bg-tertiary text-sm">
          <button onClick={() => { setQuery(item); remember(item); }} className="px-3 py-2 hover:text-accent-blue">{item}</button>
          <button aria-label={`删除搜索记录：${item}`} onClick={() => saveSearchHistory(parseSearchHistory(searchHistorySnapshot()).filter(value => value !== item))} className="px-2 text-text-muted hover:text-accent-red">×</button>
        </li>)}
      </ul>}
    </section>
    {!!query.trim() && <section aria-live="polite" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      {query.trim()!==keyword || results.isLoading ? <p>正在搜索…</p> : results.isError ? <div role="alert">搜索暂时失败。<button onClick={()=>void results.refetch()} className="ml-2 text-accent-blue">重试</button></div> : results.data && <>
        {!!results.data.failed_sources.length && <p role="status" className="mb-2 text-accent-gold">暂未取得：{results.data.failed_sources.join("、")}，当前结果可能不完整。</p>}
        <p className="mb-2 text-xs text-text-muted">{results.data.total ? `找到 ${results.data.total} 项，显示前 ${results.data.data.length} 项` : "未找到匹配结果，可尝试股票代码、公司名称或板块名称。"}</p>
        <div className="max-h-80 overflow-y-auto divide-y divide-bg-tertiary">{results.data.data.map(hit=><Link key={`${hit.kind}:${hit.code}`} onClick={() => remember(keyword)} href={hit.kind==="stock"?`/stock/${hit.code}`:`/sector/${hit.code}`} className="flex flex-wrap justify-between gap-2 py-3 text-sm hover:text-accent-blue"><span>{hit.name} <span className="text-text-muted">{hit.code}</span></span><span>{labels[hit.kind]}</span></Link>)}</div>
      </>}
    </section>}
    {showGainers && <DiscoveryRankings/>}
  </div>;
}
