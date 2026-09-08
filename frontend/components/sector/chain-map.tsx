"use client";

import type { ChainEvidence } from "@/lib/types/market";

export function ChainMap({ evidence }: { evidence?: ChainEvidence | null }) {
  if (!evidence) return <p className="text-sm text-text-muted text-center py-8">该板块尚未收录可核验的产业链资料</p>;
  const sources = (ids: string[]) => <details className="mt-3 text-xs text-text-muted">
    <summary className="cursor-pointer text-accent-blue">查看依据</summary>
    {evidence.sources.filter((source) => ids.includes(source.id)).map((source) =>
      <div key={source.id} className="mt-2 space-y-1 leading-relaxed">
        <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">{source.title}</a>
        <p>{source.publisher} · 发布 {source.published_on}</p>
        <p>核验 {source.checked_on} · {source.locator}</p>
      </div>)}
  </details>;
  return <div className="space-y-4">
    <p className="text-sm text-text-secondary leading-relaxed">{evidence.scope}</p>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
      {evidence.nodes.map((node, index) => <article key={node.id} className="rounded-lg border border-bg-tertiary bg-bg-primary/50 p-4">
        <p className="text-xs text-accent-blue mb-2">{index + 1} · {node.stage} · {node.kind === "company" ? "企业" : "产业环节"}</p>
        <h3 className="font-semibold text-text-primary">{node.label}</h3>
        {node.stock_code && <a href={`/stock/${node.stock_code}`} className="text-xs text-accent-blue">{node.stock_code}</a>}
        {sources(node.source_ids)}
      </article>)}
    </div>
    {evidence.edges.length > 0 && <section className="space-y-3" aria-label="已核验关系">
      {evidence.edges.map((edge) => <div key={`${edge.source_node}:${edge.target_node}:${edge.relation}`} className="border-t border-bg-tertiary pt-3 text-sm">
        <p>{evidence.nodes.find((node) => node.id === edge.source_node)?.label} → {evidence.nodes.find((node) => node.id === edge.target_node)?.label}</p>
        <p className="text-text-muted">{edge.relation === "supplies" ? "供货关系" : "产业环节顺序"}：{edge.description}</p>
        {sources(edge.source_ids)}
      </div>)}
    </section>}
  </div>;
}
