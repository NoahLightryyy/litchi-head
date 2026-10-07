"use client";

import { useId, useState } from "react";
import { ArrowDown, ExternalLink } from "lucide-react";
import type { ChainInterpretation } from "@/lib/chain-interpretation";
import type { ChainEvidence } from "@/lib/types/market";

type Interpretation = ChainInterpretation["interpretation"];

export function ChainMap({ evidence, interpretation }: { evidence?: ChainEvidence | null; interpretation?: Interpretation }) {
  if (!evidence) return <p className="text-sm text-text-muted text-center py-8">该板块尚未收录可核验的产业链资料</p>;
  return <EvidenceMap key={evidence.sector_code} evidence={evidence} interpretation={interpretation} />;
}

function EvidenceMap({ evidence, interpretation }: { evidence: ChainEvidence; interpretation?: Interpretation }) {
  const isMarket = evidence.map_kind === "market_structure";
  const [selection, setSelection] = useState({ kind: "node", index: 0 });
  const panelId = useId();
  const edge = selection.kind === "edge" ? evidence.edges[selection.index] : undefined;
  const node = !edge ? evidence.nodes[selection.index] ?? evidence.nodes[0] : undefined;
  const title = edge
    ? `${evidence.nodes.find((item) => item.id === edge.source_node)?.stage} → ${evidence.nodes.find((item) => item.id === edge.target_node)?.stage}`
    : node?.stage;
  const explanation = !edge && interpretation?.stages.find((stage) => stage.node_id === node?.id);
  const sourceIds = edge?.source_ids ?? node?.source_ids ?? [];
  const sources = evidence.sources.filter((source) => sourceIds.includes(source.id));

  return <div className="space-y-4">
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="rounded-full bg-accent-blue/10 px-3 py-1 text-accent-blue">{evidence.nodes.length} 个{isMarket ? "节点" : "环节"}</span>
      <span className="text-text-muted">{evidence.edges.length} 条已核验关系 · 点击{isMarket ? "节点" : "环节"}或箭头查看依据</span>
    </div>
    {isMarket && <p className="rounded-md bg-bg-primary p-3 text-sm leading-relaxed text-text-secondary">{evidence.scope.split("。")[0]}。</p>}
    <details className="text-xs text-text-muted leading-relaxed">
      <summary className="cursor-pointer">资料范围 · {evidence.sources.map((source) => source.published_on.slice(0, 4)).filter((year, index, years) => years.indexOf(year) === index).join(" / ")} 年</summary>
      <p className="pt-2">{evidence.scope}</p>
    </details>

    <div className="relative" style={{ height: evidence.nodes.length * 100 - 20 }} aria-label={isMarket ? "市场上市关系图" : "产业结构关系图"}>
      <svg className="absolute left-0 top-0 h-full w-10 overflow-visible text-accent-blue/35" aria-hidden="true">
        {evidence.edges.map((item, index) => {
          const from = evidence.nodes.findIndex((n) => n.id === item.source_node);
          const to = evidence.nodes.findIndex((n) => n.id === item.target_node);
          const start = from * 100 + 40;
          const end = to * 100 + 40;
          return <path key={index} d={Math.abs(from - to) === 1 ? `M 18 ${start} L 18 ${end}` : `M 18 ${start} C -12 ${start}, -12 ${end}, 18 ${end}`}
            fill="none" stroke="currentColor" strokeWidth={selection.kind === "edge" && selection.index === index ? 3 : 2} />;
        })}
      </svg>
      {evidence.nodes.map((item, index) => {
        const active = node?.id === item.id;
        return <div key={item.id} className="absolute left-0 right-0 flex items-center gap-4" style={{ top: index * 100, height: 80 }}>
          <span className={`z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${active ? "border-accent-blue bg-accent-blue text-bg-secondary" : "border-bg-tertiary bg-bg-secondary text-text-muted"}`}>{String(index + 1).padStart(2, "0")}</span>
          <button type="button" aria-pressed={active} aria-controls={panelId} onClick={() => setSelection({ kind: "node", index })}
            className={`h-full min-w-0 flex-1 rounded-lg border px-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-accent-blue ${active ? "border-accent-blue/60 bg-accent-blue/10" : "border-bg-tertiary bg-bg-primary/50 hover:border-accent-blue/40"}`}>
            <span className="block text-xs text-accent-blue mb-1">{item.stage}</span>
            <span className="block text-sm font-semibold text-text-primary leading-snug">{item.label}</span>
          </button>
        </div>;
      })}
      {evidence.edges.map((item, index) => {
        const from = evidence.nodes.findIndex((n) => n.id === item.source_node);
        const to = evidence.nodes.findIndex((n) => n.id === item.target_node);
        return <button key={index} type="button" aria-label={`查看关系：${evidence.nodes[from]?.stage}到${evidence.nodes[to]?.stage}`}
          aria-pressed={edge === item} aria-controls={panelId} onClick={() => setSelection({ kind: "edge", index })}
          style={{ top: ((from + to) * 100) / 2 + 28, left: Math.abs(from - to) === 1 ? 6 : -10 }}
          className={`absolute z-20 flex h-6 w-6 items-center justify-center rounded-full border focus-visible:outline-2 focus-visible:outline-accent-blue ${edge === item ? "border-accent-blue bg-accent-blue text-bg-secondary" : "border-bg-tertiary bg-bg-secondary text-accent-blue hover:bg-accent-blue/10"}`}>
          <ArrowDown className={`h-3 w-3 ${to < from ? "rotate-180" : ""}`} />
        </button>;
      })}
    </div>

    <section id={panelId} aria-label="选中环节与依据" className="rounded-lg border border-accent-blue/20 bg-accent-blue/5 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        <span className="text-xs text-text-muted">{edge ? edge.relation === "supplies" ? "供货关系" : edge.relation === "listing_relationship" ? "上市关系" : "产业环节顺序" : isMarket ? "市场结构节点" : node?.kind === "company" ? "企业" : "产业环节"}</span>
      </div>
      <p className="text-sm text-text-secondary leading-relaxed">{edge?.description ?? node?.label}</p>
      {explanation && <div className="mt-3 border-t border-accent-blue/20 pt-3">
        <p className="text-xs text-accent-blue mb-1">AI 环节解读 · 未经人工复核</p>
        <p className="text-sm text-text-secondary leading-relaxed">{explanation.explanation}</p>
      </div>}
      {node?.stock_code && <a href={`/stock/${node.stock_code}`} className="text-xs text-accent-blue">查看个股 {node.stock_code}</a>}
      <details key={`${selection.kind}-${selection.index}`} className="mt-3 text-xs text-text-muted">
        <summary className="cursor-pointer text-accent-blue">查看依据 · {sources.length} 份资料</summary>
        <div className="mt-3 space-y-3">
          {sources.map((source) => <div key={source.id} className="border-t border-bg-tertiary pt-3 leading-relaxed">
            <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">{source.title}<ExternalLink className="ml-1 inline h-3 w-3" /></a>
            <p className="mt-1">{source.publisher} · 发布 {source.published_on}</p>
            <p>核验 {source.checked_on} · {source.locator}</p>
          </div>)}
        </div>
      </details>
    </section>
  </div>;
}
