"use client";

import { useEffect, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { mapMatchesSector, mapTitle, type MapView, type MapVersion } from "@/lib/sector-map";

const button = "rounded-md border border-accent-blue/40 px-3 py-2 text-sm text-accent-blue disabled:opacity-50";
const stamp = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });

export function GeneratedMap({ sectorId }: { sectorId: string }) {
  const client = useQueryClient();
  const [version, setVersion] = useState<number | undefined>();
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);
  const path = `/market/sector/${sectorId}/map`;
  const queryKey = ["sector-generated-map", sectorId, version];
  const query = useQuery({ queryKey, queryFn: async () => {
    const result = await api.getRaw<MapView>(path, version ? { version: String(version) } : undefined);
    if (!mapMatchesSector(result, sectorId)) throw new Error("地图板块身份不匹配，请重新读取");
    return result;
  }, staleTime: 60_000, retry: false });
  const generation = useMutation({ mutationFn: async () => {
    const result = await api.postRaw<MapView>(path, {}, { signal: AbortSignal.timeout(190_000) });
    if (!mapMatchesSector(result, sectorId)) throw new Error("返回的地图板块身份不匹配");
    return result;
  }, retry: false, onSuccess: (result) => {
    client.setQueryData(["sector-generated-map", sectorId, undefined], result);
    setVersion(undefined);
  } });
  const current = query.data?.current;
  return <div className="space-y-4">
    <p className="text-xs text-text-muted">资料驱动地图 · AI 推断，待人工复核 · 自动更新尚未启用</p>
    {offline && <p role="status" className="text-sm text-accent-yellow">当前离线，已加载的版本仍可查看。</p>}
    {query.isPending && <p role="status">正在读取地图记录…</p>}
    {query.isError && <div role="alert" className="text-sm text-accent-red">
      {query.error.message} <button className={button} onClick={() => void query.refetch()}>重新读取</button>
    </div>}
    {generation.isError && <p role="alert" className="text-sm text-accent-red">{generation.error.message}；已有版本仍保留。</p>}
    {!current && !query.isPending && !query.isError && <p className="text-sm text-text-secondary">
      尚未生成此板块的资料地图。可采集成分公司披露节选，生成带原文引用的结构图。
    </p>}
    <div className="flex flex-wrap items-center gap-3">
      <button className={button} disabled={generation.isPending || offline || query.isPending || query.isError}
        onClick={() => generation.mutate()}>
        {generation.isPending ? "正在采集资料并生成…" : current ? "检查资料并更新地图" : "生成资料地图"}
      </button>
      {!!query.data?.history.length && <label className="text-xs text-text-secondary">历史版本 <select
        aria-label="地图历史版本" className="rounded border border-bg-tertiary bg-bg-secondary p-2"
        value={version ?? "latest"} onChange={(event) => setVersion(event.target.value === "latest" ? undefined : Number(event.target.value))}>
        <option value="latest">最新版本</option>
        {query.data.history.map((item) => <option key={item.version} value={item.version}>v{item.version} · {stamp(item.generated_at)}</option>)}
      </select></label>}
    </div>
    {generation.isPending && <p role="status" aria-live="polite" className="text-xs text-text-muted">
      正在读取公司披露与生成地图，最多约三分钟。请保持页面打开；不会自动重复调用 AI。
    </p>}
    {current && <CandidateMap key={`${sectorId}:${current.version}`} value={current} />}
  </div>;
}

function CandidateMap({ value }: { value: MapVersion }) {
  const [selected, setSelected] = useState({ kind: "node", index: 0 });
  const marker = useId().replaceAll(":", "");
  const { nodes, edges } = value.graph;
  const item = selected.kind === "node" ? nodes[selected.index] : edges[selected.index];
  return <div className="space-y-4">
    <h3 className="font-semibold">{value.evidence.sector_name} · {mapTitle(value.graph.map_kind)}</h3>
    <p className="text-xs text-text-muted">版本 {value.version} · 生成 {stamp(value.generated_at)}（北京时间）</p>
    <p className="text-sm text-text-secondary">{value.graph.scope}</p>
    <div className="relative" style={{ height: nodes.length * 96 }} aria-label="AI候选结构图">
      <svg className="absolute left-0 top-0 h-full w-10 overflow-visible text-accent-blue" aria-hidden="true">
        <defs><marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>
        {edges.map((edge, index) => {
          const from = nodes.findIndex((node) => node.id === edge.source) * 96 + 40;
          const to = nodes.findIndex((node) => node.id === edge.target) * 96 + 40;
          return <path key={index} d={`M 28 ${from} C -12 ${from}, -12 ${to}, 28 ${to}`}
            stroke="currentColor" fill="none" strokeDasharray="4 3" markerEnd={`url(#${marker})`} />;
        })}
      </svg>
      {nodes.map((node, index) => <button key={node.id} type="button"
        onClick={() => setSelected({ kind: "node", index })} aria-pressed={selected.kind === "node" && selected.index === index}
        className="absolute left-10 right-0 h-20 rounded-lg border border-accent-blue/30 bg-bg-primary px-3 text-left focus-visible:outline-2"
        style={{ top: index * 96 }}><span className="block text-sm font-semibold">{node.label}</span>
        <span className="text-xs text-text-muted">AI 推断 · 点击查看原文依据</span></button>)}
    </div>
    <div className="flex flex-wrap gap-2" aria-label="地图关系">
      {edges.map((edge, index) => <button key={index} className={button}
        aria-pressed={selected.kind === "edge" && selected.index === index}
        onClick={() => setSelected({ kind: "edge", index })}>
        {nodes.find((node) => node.id === edge.source)?.label} → {nodes.find((node) => node.id === edge.target)?.label}
      </button>)}
      {!edges.length && <p className="text-xs text-text-muted">资料未支持环节连线，当前仅展示有依据的节点。</p>}
    </div>
    {item && <section className="rounded-lg border border-bg-tertiary p-3 text-sm" aria-label="地图说明及引用">
      <p>{item.explanation}</p>
      <p className="mt-2 text-xs text-text-muted">AI 推断，引用匹配不等于关系已核实。</p>
      {item.citations.map((citation, index) => {
        const source = value.evidence.sources.find((entry) => entry.id === citation.source_id);
        return <details key={index} className="mt-3"><summary className="cursor-pointer text-accent-blue">原文依据：{source?.stock_code} · {source?.title}</summary>
          <blockquote className="my-2 border-l-2 pl-3">{citation.quote}</blockquote>
          <p className="text-xs">发布日期：{source?.published_on ?? "来源未标注"}</p>
          <a className="text-accent-blue underline" href={source?.url} target="_blank" rel="noopener noreferrer">打开来源</a>
        </details>;
      })}
    </section>}
    <details className="text-xs text-text-muted"><summary className="cursor-pointer">采集范围与缺口 · {value.evidence.sources.length} 份节选</summary>
      <p className="mt-2">采集 {stamp(value.evidence.collected_at)}（北京时间）；板块 {value.evidence.member_count} 家成分，尝试采集 {value.evidence.sampled_codes.join("、")}。</p>
      <ul className="mt-2 list-disc pl-4">{value.evidence.gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul>
    </details>
  </div>;
}
