"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Network, Sparkles } from "lucide-react";
import { api } from "@/lib/api/client";
import { parseCompanyResearch, type CitedInsight, type CompanyResearch } from "@/lib/company-research";

const time = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });

function Insight({ insight, result }: { insight: CitedInsight; result: CompanyResearch }) {
  return <div className="space-y-2">
    <p className="text-sm leading-7 text-text-primary whitespace-pre-line break-words">
      {insight.basis === "disclosed" && <span className="text-text-muted">按所引资料口径：</span>}{insight.text}
    </p>
    {insight.stock_impact && <div className="rounded-md border border-accent-blue/15 bg-accent-blue/5 p-3 space-y-2 text-sm leading-6">
      <p className="font-medium">对股票的可能影响 <span className="text-xs font-normal text-text-muted">条件性 AI 推断</span></p>
      <p><span className="text-text-muted">影响路径：</span>{insight.stock_impact.mechanism}</p>
      <p><span className="text-text-muted">观察周期：</span>{insight.stock_impact.horizon}</p>
      <p><span className="text-text-muted">成立与失效条件：</span>{insight.stock_impact.conditions}</p>
    </div>}
    <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
      <span>{insight.basis === "disclosed" ? "资料整理 · 未独立核验" : "AI 推断"}</span>
      {insight.source_ids.map((id) => <a key={id} href={`#company-${result.stock_code}-${id}`}
        className="text-accent-blue underline underline-offset-2">
        {result.sources.find((source) => source.id === id)?.title}
      </a>)}
    </div>
  </div>;
}

export function CompanyResearchPanel({ code }: { code: string }) {
  const client = useQueryClient();
  const queryKey = ["company-research", code];
  const saved = useQuery({
    queryKey,
    queryFn: async () => {
      if (!navigator.onLine) throw new Error("当前网络已断开，联网后可读取已保存的公司解读");
      return parseCompanyResearch(await api.getRaw<unknown>(`/stocks/${code}/company-research`), code);
    },
    networkMode: "always",
    retry: false,
    staleTime: 60_000,
  });
  const generate = useMutation({
    networkMode: "always",
    mutationFn: async () => {
      if (!navigator.onLine) throw new Error("当前网络已断开，联网后可生成公司解读");
      const value = await api.postRaw<unknown>(`/stocks/${code}/company-research`, {},
        { signal: AbortSignal.timeout(120_000) });
      const result = parseCompanyResearch(value, code);
      if (!result) throw new Error("未取得公司解读，请重试");
      return result;
    },
    onSuccess: (result) => client.setQueryData(queryKey, result),
    onError: () => { void saved.refetch(); },
    retry: false,
  });
  const result = saved.data;
  return <section aria-label="公司生态位、竞争与风险" className="min-w-0 rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="flex items-center gap-2 font-semibold"><Network className="h-5 w-5 text-accent-blue" />公司生态位、竞争与风险</h2>
        <p className="mt-1 text-xs text-text-muted">业务定位、产业链位置、竞争优势与压力，以及需要跟踪的风险</p>
      </div>
      <button type="button" disabled={generate.isPending || saved.isPending}
        onClick={() => generate.mutate()}
        className="flex items-center gap-2 rounded-md bg-accent-blue px-3 py-2 text-sm text-white disabled:opacity-50">
        <Sparkles className="h-4 w-4" />
        {generate.isPending ? "正在解读资料…" : result ? "更新解读" : "生成公司解读"}
      </button>
    </div>

    {saved.isPending && <p role="status" className="text-sm text-text-muted">正在读取已保存的解读…</p>}
    {(saved.isError || generate.isError) && <div role="alert" className="rounded-md border border-accent-red/30 bg-accent-red/5 p-3 text-sm">
      <p>{generate.error?.message || saved.error?.message}</p>
      {result && <p className="mt-1 text-text-muted">下方保留上次成功的解读，生成时间未更新。</p>}
      {(result || saved.isError) && <button type="button" onClick={() => void saved.refetch()} disabled={saved.isFetching}
        className="mt-2 text-accent-blue underline">
        {result ? "重新读取已保存结果" : "重试读取历史记录"}</button>}
    </div>}
    {generate.isPending && <p role="status" className="text-sm text-text-muted">正在读取公司资料和定期报告并生成解读，通常需要约一分钟。成功后自动保存。</p>}
    {!result && !saved.isPending && !generate.isPending && !saved.isError && !generate.isError && <p className="rounded-md bg-bg-primary p-4 text-sm leading-7 text-text-secondary">
      点击“生成公司解读”，查看该公司的业务定位、产业链位置、亮点、竞争点和风险点。每项附资料出处，生成后再次打开本页仍可查看。
    </p>}

    {result && <div className="space-y-5">
      <div className="text-xs text-text-muted space-y-1">
        <p>{result.company_name} · AI 解读，未经人工复核</p>
        <p>已保存 · 生成于 {time(result.generated_at)}（北京时间）</p>
        <p>依据以下资料节选，不代表最新完整信息或投资建议。</p>
      </div>
      <div className="rounded-md bg-accent-blue/5 border border-accent-blue/20 p-4">
        <Insight insight={result.interpretation.niche} result={result} />
      </div>
      <div className="space-y-3">
        <h3 className="font-medium text-sm">产业链位置 <span className="ml-2 font-normal text-xs text-text-muted">一般业务环节示意</span></h3>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          {([['上游', result.interpretation.upstream], ['本公司', result.interpretation.role], ['下游', result.interpretation.downstream]] as const).map(([label, insight]) =>
            <div key={label} className={`min-w-0 rounded-md border p-4 ${label === "本公司" ? "border-accent-blue/30 bg-accent-blue/5" : "border-bg-tertiary bg-bg-primary"}`}>
              <p className="mb-3 text-sm font-medium text-accent-blue">{label}</p>
              <Insight insight={insight} result={result} />
            </div>)}
        </div>
      </div>
      <p className="text-xs text-text-muted leading-6">经营优势或风险会通过盈利预期、估值等影响股价；市场可能已经反映这些预期。以下解释影响路径与条件，不代表必然涨跌。</p>
      {[...result.interpretation.highlights, ...result.interpretation.watchpoints, ...(result.interpretation.competition ?? [])].some(item => !item.stock_impact) && <p className="text-sm text-text-muted">这份历史解读尚未补全股票影响，点击“更新解读”生成。</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {([['业务亮点', result.interpretation.highlights], ['竞争点 · 优势与压力', result.interpretation.competition ?? []], ['风险点 · 影响与观察信号', result.interpretation.watchpoints]] as const).map(([title, items]) =>
          <div key={title} className="space-y-3">
            <h3 className="font-medium">{title}</h3>
            {items.length === 0 && <p className="text-sm text-text-muted">这份历史解读尚未生成竞争点，点击“更新解读”补充。</p>}
            <ul className="space-y-4">{items.map((insight, index) => <li key={index} className="border-l-2 border-bg-tertiary pl-3"><Insight insight={insight} result={result} /></li>)}</ul>
          </div>)}
      </div>
      {result.gaps.length > 0 && <div className="rounded-md bg-bg-primary p-3 text-xs leading-6 text-text-secondary">
        <p className="font-medium">本次资料范围</p>
        {result.gaps.map((gap, index) => <p key={index}>{gap}</p>)}
      </div>}
      <div className="space-y-3 border-t border-bg-tertiary pt-4">
        <h3 className="text-sm font-medium">资料出处与引用原文</h3>
        {result.sources.map((source) => <div id={`company-${code}-${source.id}`} key={source.id} className="scroll-mt-6 text-xs space-y-2">
          <div className="flex flex-wrap gap-2">
            <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">{source.title} ↗</a>
            <span className="text-text-muted">{source.published_at ? `公告日期 ${source.published_at}` : "更新日期未提供"}</span>
          </div>
          <details className="text-text-secondary">
            <summary className="cursor-pointer">查看本次使用的资料节选</summary>
            <p className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-bg-primary p-3 leading-6">{source.excerpt}</p>
          </details>
        </div>)}
        <p className="text-xs text-text-muted">采集于 {time(result.fetched_at)}（北京时间）· {result.model}</p>
      </div>
    </div>}
  </section>;
}
