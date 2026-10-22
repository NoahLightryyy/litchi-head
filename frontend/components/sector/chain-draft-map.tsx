"use client";
import {useId} from 'react';
import {useQuery} from '@tanstack/react-query';
import {chainDraftRecovery} from '@/lib/chain-draft-query';
import {api} from '@/lib/api/client';
import {parseChainDraft} from '@/lib/chain-draft';

export function ChainDraftMap({code,name}:{code:string;name:string}) {
  const arrowId=useId();
  const query=useQuery({queryKey:['chain-draft',code,name],...chainDraftRecovery,
    queryFn:async()=>{
      return parseChainDraft(await api.postRaw<unknown>(`/market/sector/${encodeURIComponent(code)}/chain-draft`,
        {sector_name:name},{signal:AbortSignal.timeout(100_000)}),code,name);
    }});
  const result=query.data;
  return <section aria-label="AI结构草图" className="space-y-4">
    <header><h3 className="font-semibold">{name} · AI{result?.graph.map_kind==='concept_structure'?'概念结构':'产业结构'}草图</h3>
      <p className="mt-2 text-xs text-text-muted">暂无已核验地图，AI先绘制研究草图。节点与连线均为待核验推断，不代表真实公司供货关系。</p></header>
    {query.fetchStatus==='paused' && <p role="status" className="text-sm">当前离线，恢复网络后可继续绘图。</p>}
    {query.isFetching && <p role="status" className="animate-pulse text-sm text-accent-blue">{query.failureCount>0 ? '请求暂未成功，正在自动恢复，请稍候…' : 'AI 正在梳理环节、绘制关系并保存结果，通常需要几十秒…'}</p>}
    {query.isError && <div role="alert" className="text-sm text-accent-red"><p>{query.error instanceof Error ? query.error.message : 'AI绘图请求未成功，请稍后重试'}</p><button className="mt-3 rounded border px-3 py-2" onClick={()=>void query.refetch()} disabled={query.isFetching}>重试 AI 绘图</button></div>}
    {result && <>
      <p className="rounded bg-accent-gold/10 p-3 text-sm">AI推断 · 未经来源核验<br/>{result.graph.scope}</p>
      <p className="text-xs text-text-muted">{result.model} · {new Date(result.generated_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}（北京时间） · {result.cached?'已保存草图':'本次生成，已保存'}</p>
      <div className="relative space-y-4 pl-10" aria-label="AI推断环节">
        <svg className="absolute left-0 top-0 h-full w-10 overflow-visible text-accent-blue/60" viewBox={`0 0 40 ${result.graph.nodes.length*160-16}`} preserveAspectRatio="none" aria-hidden="true">
          <defs><marker id={arrowId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>
          {result.graph.edges.map(e=>{const from=result.graph.nodes.findIndex(n=>n.id===e.source)*160+65,to=result.graph.nodes.findIndex(n=>n.id===e.target)*160+65;return <path key={`${e.source}:${e.target}`} d={`M 34 ${from} C 4 ${from},4 ${to},34 ${to}`} fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" markerEnd={`url(#${arrowId})`} />;})}
        </svg>
        {result.graph.nodes.map((n,i)=><article key={n.id} className="h-36 overflow-y-auto rounded-lg border border-dashed border-accent-blue/50 bg-accent-blue/5 p-4">
          <h4 className="font-semibold text-sm"><span className="text-accent-blue">{i+1} · </span>{n.label}</h4><p className="mt-2 text-sm">{n.role}</p>
          <details className="mt-3 text-xs text-text-muted"><summary className="cursor-pointer">需要核验什么</summary><p className="mt-2">{n.verify}</p></details>
        </article>)}
      </div>
      <div aria-label="AI推断关系" className="space-y-3">{result.graph.edges.map(e=><div key={`${e.source}:${e.target}`} className="border-l-2 border-dashed border-accent-blue/40 pl-3 text-sm">
        <p className="text-accent-blue">{result.graph.nodes.find(n=>n.id===e.source)?.label} <span aria-label="推断关系">⇢</span> {result.graph.nodes.find(n=>n.id===e.target)?.label}</p><p className="mt-1 text-text-secondary">{e.explanation}</p>
      </div>)}</div>
    </>}
  </section>;
}
