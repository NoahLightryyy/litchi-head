import type { RelatedDocument, RelatedKeywordOrigin, RelatedResearchResult } from "@/lib/related-research";

const origins: Record<RelatedKeywordOrigin, string> = { name: "名称", business: "主营业务", expanded: "关联主题", user: "自定", code: "代码" };
const sourceLabels = { policy_archive: "政策归档", news_archive: "报道资料库", company_profile: "主营资料" };

function DocumentCard({ item }: { item: RelatedDocument }) {
  return <article className="rounded-md border border-bg-tertiary bg-bg-primary p-3 space-y-2">
    <a className="text-sm font-medium text-accent-blue underline underline-offset-2" href={item.url} target="_blank" rel="noopener noreferrer">{item.title} ↗</a>
    <p className="text-xs text-text-muted">{item.publisher} · 发布 {item.published_at} · {sourceLabels[item.source]}</p>
    {item.excerpt && <p className="line-clamp-3 text-sm leading-6 text-text-secondary whitespace-pre-wrap">{item.excerpt}</p>}
    <p className="text-xs leading-5 text-text-muted"><span>{item.relevance === "direct" ? "名称／代码提及" : "主题相关"}</span> · {item.reason}</p>
    <p className="text-xs text-text-muted">匹配词：{item.matched_keywords.join("、")}</p>
  </article>;
}

function DocumentGroup({ title, items }: { title: string; items: RelatedDocument[] }) {
  if (!items.length) return null;
  return <section aria-label={title} className="space-y-3">
    <h4 className="text-sm font-semibold">{title} <span className="font-normal text-text-muted">{items.length} 篇</span></h4>
    {items.slice(0, 3).map(item => <DocumentCard key={item.id} item={item} />)}
    {items.length > 3 && <details className="text-sm">
      <summary className="cursor-pointer text-accent-blue">展开其余 {items.length - 3} 篇{title}</summary>
      <div className="mt-3 space-y-3">{items.slice(3).map(item => <DocumentCard key={item.id} item={item} />)}</div>
    </details>}
  </section>;
}

export interface RelatedResearchContentProps {
  data?: RelatedResearchResult;
  pending: boolean;
  failed: boolean;
  paused: boolean;
  error?: string;
  onKeyword: (term: string) => void;
}
export function RelatedResearchContent({ data, pending, failed, paused, error, onKeyword }: RelatedResearchContentProps) {
  return <div className="space-y-4">
    {paused ? <p role="status" className="text-sm text-text-muted">当前离线。{data ? "保留上次同条件检索结果。" : "联网后可继续检索。"}</p>
      : pending ? <p role="status" className="text-sm text-text-muted">正在查找相关政策与资讯…</p>
      : failed && <p role="alert" className="text-sm">{error || "相关资料检索暂不可用，请重试。"}{data && "保留上次同条件检索结果，检索时间未更新。"}</p>}
    {data && <>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-text-muted">{data.query ? "本次检索词" : "自动提词"}</span>
        {data.keywords.map(keyword => <button key={`${keyword.origin}:${keyword.term}`} type="button" onClick={() => onKeyword(keyword.term)} className="rounded-full border border-bg-tertiary px-2.5 py-1 text-accent-blue" title={`按“${keyword.term}”单独检索`}>
          {keyword.term} <span className="text-text-muted">· {origins[keyword.origin]}</span>
        </button>)}
      </div>
      {data.status === "empty" && <p className="rounded-md bg-bg-primary p-3 text-sm text-text-secondary">现有资料库中暂无匹配内容，可调整关键词。没有检索结果不代表没有相关政策。</p>}
      {data.status === "partial" && <p className="text-xs text-text-muted">部分资料源暂不可用，先展示已找到的内容。</p>}
      <DocumentGroup title="政策相关资料" items={data.data.filter(item => item.category === "policy")} />
      <DocumentGroup title="相关报道" items={data.data.filter(item => item.category === "report")} />
      <p className="text-xs text-text-muted">检索时间（北京时间）：{new Date(data.searched_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })} · 近 {data.window_days} 天报道及已归档政策</p>
      <details className="text-xs text-text-muted leading-6">
        <summary className="cursor-pointer">检索范围与来源状态</summary>
        <p className="mt-2">按关键词关联，不等同于已核验的标的证据；“政策相关资料”也包含政策报道，请以链接原文为准。</p>
        {data.limitations.map((limitation, index) => <p key={index}>{limitation}</p>)}
        <ul>{data.sources.map(source => <li key={source.source}>{sourceLabels[source.source]}：{{ ok: "可用", unavailable: "暂不可用", not_requested: "本次未调用" }[source.status]}{source.message && ` · ${source.message}`}</li>)}</ul>
      </details>
    </>}
  </div>;
}
