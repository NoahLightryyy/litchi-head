"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseChainInterpretation } from "@/lib/chain-interpretation";
import type { ChainEvidence } from "@/lib/types/market";
import { ChainMap } from "./chain-map";

export function ChainExplorer({ evidence }: { evidence?: ChainEvidence | null }) {
  if (!evidence) return <ChainMap evidence={evidence} />;
  return <EvidenceExplorer key={JSON.stringify(evidence)} evidence={evidence} />;
}

function EvidenceExplorer({ evidence }: { evidence: ChainEvidence }) {
  const subject = evidence.map_kind === "market_structure" ? "市场结构" : "产业链";
  const analysis = useMutation({
    mutationFn: async () => {
      if (!navigator.onLine) throw new Error("当前网络已断开，联网后可生成 AI 解读；资料图仍可查看");
      const response = await api.postRaw<unknown>(
        `/market/sector/${evidence.sector_code}/chain-analysis`, {},
        { signal: AbortSignal.timeout(55_000) },
      );
      return parseChainInterpretation(response, evidence);
    },
    retry: false,
  });
  const result = analysis.data;
  return <div className="space-y-4">
    <div className="rounded-lg border border-accent-blue/20 bg-accent-blue/5 p-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">AI {subject}解读</h3>
        <button type="button" onClick={() => analysis.mutate()} disabled={analysis.isPending || !!result}
          className="rounded-md bg-accent-blue px-3 py-2 text-xs font-medium text-white disabled:opacity-50">
          {analysis.isPending ? "正在生成…" : result ? "解读已生成" : analysis.isError ? "重试 AI 解读" : "生成 AI 解读"}
        </button>
      </div>
      {!result && <p className="text-xs text-text-muted">根据下方核验资料解释各环节。点击生成后，可在图中查看对应解读。</p>}
      {analysis.isPending && <p role="status" className="text-xs text-text-muted">AI 正在解读资料，通常需要数十秒；结构图可继续查看。</p>}
      {analysis.isError && <p role="alert" className="text-xs text-accent-red">{analysis.error.message}</p>}
      {result && <section aria-label={`AI ${subject}解读结果`} className="space-y-2">
        <p className="text-xs text-text-muted">AI 解读 · 未经人工复核 · 引用覆盖 100%（不代表准确率）</p>
        <p className="text-sm leading-relaxed text-text-secondary whitespace-pre-line">{result.interpretation.summary}</p>
        <p className="text-xs text-text-muted">{result.model} · {new Date(result.generated_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}（北京时间） {result.cached ? "· 已缓存的解读" : ""}</p>
      </section>}
    </div>
    <ChainMap evidence={evidence} interpretation={result?.interpretation} />
  </div>;
}
