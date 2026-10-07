"use client";
import {useState} from "react";
import {useQuery, useQueryClient} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {useDebounce} from "@/lib/hooks/use-debounce";

type Article={id:string;channel:string;title:string;date:string;source:string;url:string};
type Coverage={channel:string;source:string;count:number;oldest:string|null;newest:string|null;last_success:string|null;history_status:string;error:string|null};
type ArchivePage={data:Article[];total:number;page:number;page_size:number;start_at:string;end_at:string;coverage:Coverage[];limitations:string[]};
const statusNames:Record<string,string>={pending:"待采集",running:"继续补抓历史",failed:"采集失败，保留缺口",stalled:"历史返回重复页，已停止",exhausted:"接口已无更多历史",window_limit:"已到三年补抓边界"};
const date=(value:string|null)=>value?new Date(value).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false}):"尚未取得";
const safeLink=(value:string)=>/^https?:\/\//i.test(value)?value:null;

export function NewsArchive(){
  const client=useQueryClient();
  const [days,setDays]=useState("7");
  const [channel,setChannel]=useState("");
  const [input,setInput]=useState("");
  const query=useDebounce(input.trim(),300);
  const [paging,setPaging]=useState({key:"",page:1,asOf:""});
  const key=[days,channel,query].join("|");
  const page=paging.key===key?paging.page:1;
  const asOf=paging.key===key?paging.asOf:"";
  const params=new URLSearchParams({days,channel,q:query,page:String(page),as_of:asOf});
  const result=useQuery({queryKey:["news-archive",days,channel,query,page,asOf],queryFn:()=>api.getRaw<ArchivePage>(`/news-archive?${params}`),retry:false,staleTime:60000});
  const move=(next:number)=>setPaging({key,page:next,asOf:result.data?.end_at??asOf});
  return <section className="space-y-4 rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
    <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">新闻资料库</h2><button disabled={result.isFetching} className="text-sm text-accent-blue" onClick={()=>{setPaging({key:"",page:1,asOf:""});void client.invalidateQueries({queryKey:["news-archive"]});}}>更新入库状态</button></div>
    <p className="text-xs text-text-muted">应用运行时持续采集并分页补抓历史，重启后保留。这里检索已保存的报道，不再限于当前快讯的100条样本。所有时间为北京时间。</p>
    <div className="flex flex-wrap gap-3 text-sm">
      <label>时间范围 <select aria-label="资料库时间范围" value={days} onChange={e=>setDays(e.target.value)} className="rounded border border-bg-tertiary bg-bg-primary p-2">{[["1","近24小时"],["7","近7天"],["93","近3个月"],["365","近1年"],["1095","近3年"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label>渠道 <select aria-label="资料库渠道" value={channel} onChange={e=>setChannel(e.target.value)} className="rounded border border-bg-tertiary bg-bg-primary p-2"><option value="">全部</option>{[["caixin","财新"],["sina","新浪"],["eastmoney","东方财富"],["cls","财联社"],["ths","同花顺"],["futu","富途"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <input maxLength={80} aria-label="资料库关键词" placeholder="公司、代码或事件关键词" value={input} onChange={e=>setInput(e.target.value)} className="min-w-0 rounded border border-bg-tertiary bg-bg-primary px-3 py-2"/>
    </div>
    {result.isLoading ? <p role="status">正在检索历史库…</p> : result.isError ? <div role="alert">历史库暂时不可用。<button onClick={()=>void result.refetch()} className="ml-2 text-accent-blue">重试</button></div> : result.data && <>
      <details open className="rounded border border-bg-tertiary p-3 text-xs">
        <summary className="cursor-pointer font-medium">各渠道覆盖与缺口 · 累计入库 {result.data.coverage.reduce((sum,item)=>sum+item.count,0)} 条</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{result.data.coverage.map(item=><div key={item.channel} className="rounded bg-bg-primary p-3 leading-relaxed"><strong>{item.source} · {item.count}条</strong><p>最早：{date(item.oldest)}</p><p>最新：{date(item.newest)}</p><p>{statusNames[item.history_status]??item.history_status}</p><p>最近采集：{date(item.last_success)}</p>{item.error&&<p className="text-accent-gold">{item.error}</p>}<p className="text-text-muted">完整覆盖尚未证明</p></div>)}</div>
      </details>
      <p className="text-xs text-text-muted">{result.data.limitations.join(" ")}</p>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span role="status">匹配 {result.data.total} 条 · 第 {page}/{Math.max(1,Math.ceil(result.data.total/100))} 页</span><div className="flex gap-3"><button disabled={page<=1||result.isFetching} onClick={()=>move(page-1)} className="text-accent-blue disabled:opacity-40">上一页</button><button disabled={page*100>=result.data.total||result.isFetching} onClick={()=>move(page+1)} className="text-accent-blue disabled:opacity-40">下一页</button></div></div>
      <div className="max-h-[500px] overflow-y-auto divide-y divide-bg-tertiary">{result.data.data.map(item=><article key={item.id} className="py-3"><p className="text-sm">{safeLink(item.url)?<a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-accent-blue">{item.title} ↗</a>:item.title}</p><p className="mt-2 text-xs text-text-muted">{item.source} · {date(item.date)}</p></article>)}{!result.data.data.length&&<p className="py-6 text-sm text-text-muted">当前已入库记录中没有匹配报道；不代表该时期没有相关新闻。</p>}</div>
    </>}
  </section>;
}
