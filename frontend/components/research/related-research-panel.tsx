"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Subject } from "@/lib/policy-capital";
import { fetchRelatedResearch, relatedResearchKey, relatedResearchQueryPolicy, relatedResearchRequest } from "@/lib/related-research";
import { RelatedResearchContent } from "./related-research-content";
import { RelatedInterpretationPanel } from "./related-interpretation-panel";

export function RelatedResearchPanel(props: Subject & { name: string }) {
  return <Panel key={`${props.kind}:${props.code}`} {...props} />;
}
function Panel(props: Subject & { name: string }) {
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState("");
  const request = relatedResearchRequest(props, submitted);
  const query = useQuery({
    queryKey: relatedResearchKey(request),
    ...relatedResearchQueryPolicy,
    queryFn: ({ signal }) => fetchRelatedResearch(request, signal),
  });
  function search(value: string) {
    const normalized = value.trim();
    setDraft(normalized);
    if (normalized === submitted) void query.refetch();
    else setSubmitted(normalized);
  }
  return <section aria-label="相关政策与资讯" className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="font-semibold">相关政策与资讯</h3><p className="mt-1 text-sm text-text-muted">{props.name} · {props.code} · 按名称、业务与主题查找已有资料</p></div>
      <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching || query.isPaused} className="text-sm text-accent-blue disabled:opacity-50">{query.isFetching ? "正在检索…" : "刷新资料"}</button>
    </div>
    <form onSubmit={event => { event.preventDefault(); search(draft); }} className="flex flex-wrap items-end gap-2">
      <label className="min-w-48 flex-1 text-sm">检索关键词<input aria-label="相关资料检索关键词" maxLength={80} value={draft} onChange={event => setDraft(event.target.value)} placeholder="留空自动提词；可输入行业或主营业务" className="mt-1 w-full rounded border border-bg-tertiary bg-bg-primary p-2" /></label>
      <button type="submit" disabled={query.isFetching || query.isPaused} className="rounded border border-bg-tertiary px-3 py-2 text-sm text-accent-blue disabled:opacity-50">搜索资料</button>
      <button type="button" onClick={() => search("")} disabled={query.isFetching || query.isPaused} className="rounded border border-bg-tertiary px-3 py-2 text-sm text-accent-blue disabled:opacity-50">恢复自动提词</button>
    </form>
    <p className="text-xs text-text-muted">多个关键词用空格或逗号分隔，匹配任意一个即可。「刷新资料」和「搜索资料」只做检索，不调用 AI；解读由下方按钮单独生成。</p>
    <RelatedInterpretationPanel request={request} current={query.data} />
    <RelatedResearchContent data={query.data} pending={query.isPending} failed={query.isError} paused={query.isPaused} error={query.error?.message} onKeyword={search} />
  </section>;
}
