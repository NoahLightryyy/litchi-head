"use client";

import { useState, useSyncExternalStore } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { RelatedResearchRequest, RelatedResearchResult } from "@/lib/related-research";
import { copyableRelatedInterpretation, generateRelatedInterpretation, INTERPRETATION_DIMENSIONS, INTERPRETATION_DIRECTION, readRelatedInterpretation, relatedInterpretationKey, relatedInterpretationQueryPolicy, relatedSnapshotChanged, type RelatedEvent, type RelatedInterpretationResult } from "@/lib/related-interpretation";

const button = "rounded-md border border-bg-tertiary px-3 py-2 text-sm text-accent-blue disabled:opacity-50";
const time = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
const publicationTime = (value: string) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)) ? time(value) : value;
function subscribeOnline(listener: () => void) {
  window.addEventListener("online", listener); window.addEventListener("offline", listener);
  return () => { window.removeEventListener("online", listener); window.removeEventListener("offline", listener); };
}

export function RelatedInterpretationPanel(props: { request: RelatedResearchRequest; current?: RelatedResearchResult }) {
  return <QueryInterpretationPanel key={JSON.stringify(relatedInterpretationKey(props.request))} {...props} />;
}
function QueryInterpretationPanel({ request, current }: { request: RelatedResearchRequest; current?: RelatedResearchResult }) {
  const client = useQueryClient();
  const online = useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
  const queryKey = relatedInterpretationKey(request);
  const saved = useQuery({
    queryKey, ...relatedInterpretationQueryPolicy,
    queryFn: ({ signal }) => readRelatedInterpretation(request, signal),
  });
  const generation = useMutation({
    mutationFn: (refresh: boolean) => {
      if (!navigator.onLine) throw new Error("当前离线，请联网后手动生成资料解读。");
      return generateRelatedInterpretation(request, refresh);
    },
    networkMode: "always", retry: false,
    onSuccess: async (result) => {
      try { await client.cancelQueries({ queryKey, exact: true }); }
      catch { console.warn("取消旧资料解读读取失败，继续保留新生成的结果。"); }
      client.setQueryData(queryKey, result);
    },
  });
  const error = generation.error ?? saved.error;
  return <RelatedInterpretationContent key={saved.data?.generated_at ?? "empty"}
    data={saved.data ?? null} current={current} query={request.q}
    loading={saved.isPending} reading={saved.isFetching} generating={generation.isPending}
    offline={!online || saved.isPaused} error={error instanceof Error ? error.message : null}
    canGenerate={saved.isSuccess || saved.isError || !!saved.data} readFailed={saved.isError}
    onRead={() => { generation.reset(); void saved.refetch(); }}
    onGenerate={() => generation.mutate(saved.isError || Boolean(saved.data))}
  />;
}

function EventCard({ event, result }: { event: RelatedEvent; result: RelatedInterpretationResult }) {
  const sources = result.snapshot.data.filter((source) => event.source_ids.includes(source.id));
  return <article className="min-w-0 rounded-lg border border-bg-tertiary bg-bg-primary/60 p-4 space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-2"><h5 className="font-semibold text-text-primary">{event.title}</h5><span className="rounded-full bg-bg-tertiary px-2.5 py-1 text-xs text-text-secondary">{INTERPRETATION_DIRECTION[event.impact_direction]} · 推断</span></header>
    <div className="text-sm leading-7"><p className="mb-1 text-xs font-medium text-text-muted">资料说了什么</p><p className="whitespace-pre-line break-words">{event.summary.text}</p></div>
    <dl className="grid gap-x-5 gap-y-4 sm:grid-cols-2">{INTERPRETATION_DIMENSIONS.map(([key, label]) => <div key={key} className="min-w-0"><dt className="mb-1 text-xs font-medium text-accent-blue">{label} <span className="font-normal text-text-muted">· AI 推断</span></dt><dd className="text-sm leading-6 whitespace-pre-line break-words">{event[key].text}</dd></div>)}</dl>
    <div className="text-sm"><h6 className="font-medium">接下来核查什么</h6><ul className="mt-1 list-disc pl-5 space-y-1 leading-6">{event.watchpoints.map((point, index) => <li key={index}>{point}</li>)}</ul></div>
    <ul aria-label={`${event.title}的资料来源`} className="space-y-2 border-t border-bg-tertiary pt-3 text-xs text-text-muted">{sources.map((source) => <li key={source.id}>
      <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue underline underline-offset-2">{source.title} ↗</a>
      <p className="mt-1">{source.publisher} · 发布 {publicationTime(source.published_at)} · {source.source === "policy_archive" ? "政策档案摘要" : "报道资料"}</p>
    </li>)}</ul>
    <details className="text-xs text-text-muted"><summary className="cursor-pointer">查看引用片段与原始资料范围</summary><div className="mt-3 space-y-3 leading-6">
      {event.summary.quotes.map((quote, index) => {
        const source = sources.find((item) => item.id === quote.source_id)!;
        return <div key={index}><p>{source.title} · {quote.field === "title" ? "标题" : source.source === "policy_archive" ? "档案摘要" : "报道节选"}</p><blockquote className="mt-1 border-l-2 border-bg-tertiary pl-3 whitespace-pre-wrap break-words">{quote.quote}</blockquote></div>;
      })}
      <p>引用片段来自本次保存的标题或节选，不代表已经阅读完整原文；同一事件的转载不算独立验证。</p>
    </div></details>
  </article>;
}

export interface RelatedInterpretationContentProps {
  data: RelatedInterpretationResult | null;
  current?: RelatedResearchResult;
  query: string;
  loading: boolean;
  reading: boolean;
  generating: boolean;
  offline: boolean;
  error: string | null;
  canGenerate: boolean;
  readFailed?: boolean;
  onRead: () => void;
  onGenerate: () => void;
}

export function RelatedInterpretationContent(props: RelatedInterpretationContentProps) {
  const { data, loading, reading, generating, offline, error } = props;
  const [copyMessage, setCopyMessage] = useState("");
  async function copy() {
    if (!data) return;
    try { await navigator.clipboard.writeText(copyableRelatedInterpretation(data)); setCopyMessage("研究要点已复制，包含来源和 AI 推断标记。"); }
    catch { setCopyMessage("复制未成功，可选中本页文字手动复制。"); }
  }
  return <section aria-label="政策与资讯通俗解读" className="rounded-lg border border-accent-blue/20 bg-bg-secondary p-4 space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h4 className="font-semibold">政策与资讯通俗解读</h4><p className="mt-1 text-sm text-text-muted">把相关报道按事件整理，看清产业影响、持续条件与反馈节奏。</p></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={button} disabled={reading || generating || offline} onClick={props.onRead}>{reading ? "正在读取…" : "读取已存解读"}</button>
        <button type="button" className={`${button} bg-accent-blue text-white`} disabled={!props.canGenerate || loading || generating || offline} onClick={props.onGenerate}>{generating ? "AI 正在解读…" : props.readFailed ? "AI 重新生成" : data ? "AI 更新解读" : "AI 生成解读"}</button>
      </div>
    </header>
    <p className="text-xs text-text-muted">读取已存解读不调用模型；点击 AI 生成或更新时会产生推理调用，失败不会自动重试生成。</p>
    {offline && <p role="status" className="text-sm text-text-secondary">当前离线。{data ? "保留已保存解读和原资料快照。" : "联网后可读取已保存解读。"}</p>}
    {loading && !data && !offline && <p role="status" className="text-sm text-text-muted">正在读取本标的、当前检索条件的已存解读…</p>}
    {generating && <p role="status" className="text-sm text-text-muted">正在重新检索相关资料并整理事件与影响，请勿重复提交。{data ? "下方保留上次成功解读。" : ""}</p>}
    {error && <p role="alert" className="rounded-md bg-amber-500/10 p-3 text-sm">{error}{data && " 下方保留上次成功解读，生成时间未更新。"}</p>}
    {!data && !loading && !generating && !error && <p className="text-sm text-text-secondary">尚无当前检索条件的解读。点击「AI 生成解读」，即可整理资料概况、产业传导、涉及范围、持续条件和反馈节奏。</p>}
    {data && <>
      <div className="text-xs text-text-muted space-y-1">
        <p>{data.subject_name} · {data.subject_id} · {data.query ? `检索词：${data.query}` : "自动提词资料"} · AI 解读，未经人工复核</p>
        <p>生成于 {time(data.generated_at)} · 资料快照检索于 {time(data.snapshot.searched_at)}</p>
        <p>{data.snapshot.data.length} 篇资料 · {data.analysis.events.length} 个事件 · 时刻按北京时间显示，只有日期的按来源保留</p>
      </div>
      {relatedSnapshotChanged(data, props.current) && <p role="status" className="rounded-md bg-bg-primary p-3 text-sm text-text-secondary">当前检索资料已变化；下方解读仍基于原资料快照。点击「AI 更新解读」可重新整理。</p>}
      <div className="rounded-md bg-accent-blue/5 p-3 text-sm leading-7 whitespace-pre-line break-words"><p className="mb-1 text-xs font-medium text-accent-blue">先读这段</p>{data.analysis.overview}</div>
      {data.status === "no_relevant_events" && <p className="text-sm text-text-secondary">这批资料没有适合展开的相关事件。可在下方查看排除原因，或调整关键词后重新检索。</p>}
      <div className="space-y-4" aria-label="主要相关事件">{data.analysis.events.slice(0, 3).map((event, index) => <EventCard key={index} event={event} result={data} />)}</div>
      {data.analysis.events.length > 3 && <details className="text-sm"><summary className="cursor-pointer text-accent-blue">展开其余 {data.analysis.events.length - 3} 个事件</summary><div className="mt-4 space-y-4">{data.analysis.events.slice(3).map((event, index) => <EventCard key={index} event={event} result={data} />)}</div></details>}
      <div className="flex flex-wrap items-center gap-3"><button type="button" className={button} onClick={() => void copy()}>复制研究要点</button><p className="text-xs text-text-muted">{props.query.trim() ? "自定关键词的解读可复制到后续研究中，保留来源与推断标记。" : "自动提词的已存解读会供后续辩论参考，保留资料来源与推断标记。"}</p></div>
      {copyMessage && <p role="status" className="text-xs text-text-muted">{copyMessage}</p>}
      <details className="border-t border-bg-tertiary pt-3 text-xs text-text-muted"><summary className="cursor-pointer">本次资料范围与排除原因</summary><div className="mt-3 space-y-3 leading-6">
        <p>解读使用本页保存的资料快照。事件归并与产业影响属于 AI 判断，资料概况也未经独立核验。</p>
        {data.analysis.excluded_sources.length > 0 && <ul className="space-y-2">{data.analysis.excluded_sources.map((excluded) => {
          const source = data.snapshot.data.find((item) => item.id === excluded.source_id)!;
          return <li key={excluded.source_id}><a className="text-accent-blue underline" href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a> · 发布 {publicationTime(source.published_at)}<p>未展开原因：{excluded.reason}</p></li>;
        })}</ul>}
        <ul className="list-disc pl-5 space-y-1">{[...new Set([...data.analysis.limitations, ...data.snapshot.limitations])].map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
        <p>模型 {data.model} · 提示版本 {data.prompt_version}</p>
      </div></details>
    </>}
  </section>;
}
