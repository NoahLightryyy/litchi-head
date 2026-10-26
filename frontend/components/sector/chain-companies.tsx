"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { chainCompaniesKey, parseChainCompanies, type ChainCompanies } from "@/lib/chain-companies";
import type { ChainDraft } from "@/lib/chain-draft";

const stamp = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });

export function ChainCompaniesPanel({ draft }: { draft: ChainDraft }) {
  const client = useQueryClient();
  const queryKey = chainCompaniesKey(draft);
  const fetchCompanies = async (refresh: boolean) => {
    if (!navigator.onLine) throw new Error("当前离线，联网后可继续读取企业清单。");
    return parseChainCompanies(await api.postRaw<unknown>(
      `/market/sector/${encodeURIComponent(draft.sector_code)}/chain-companies`,
      { sector_name: draft.sector_name, refresh }, { signal: AbortSignal.timeout(125_000) },
    ), draft);
  };
  const query = useQuery({ queryKey, queryFn: () => fetchCompanies(false), staleTime: Infinity,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: false, retry: false });
  const update = useMutation({ mutationFn: () => fetchCompanies(true), retry: false,
    onSuccess: async (data) => {
      try { await client.cancelQueries({ queryKey, exact: true }); }
      catch { console.warn("企业清单旧读取取消失败，仍保留本次成功结果"); }
      client.setQueryData(queryKey, data);
    },
  });
  const error = update.error ?? query.error;
  const storageFailed = (query.error as { code?: string } | null)?.code === "CHAIN_COMPANIES_STORAGE";
  return <ChainCompaniesContent draft={draft} data={query.data} loading={query.isFetching || update.isPending}
    offline={query.fetchStatus === "paused" || update.isPaused}
    error={error instanceof Error ? error.message : error ? "企业清单暂不可用" : null}
    onRetry={() => { if (query.data || storageFailed) update.mutate(); else void query.refetch(); }} />;
}

export function ChainCompaniesContent({ draft, data, loading, offline, error, onRetry }: {
  draft: ChainDraft; data?: ChainCompanies; loading: boolean; offline: boolean;
  error: string | null; onRetry: () => void;
}) {
  return <section aria-label="代表企业与影响力" className="space-y-3 border-t border-bg-tertiary pt-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="font-semibold">代表企业与影响力</h4>
      {!loading && <button className="text-xs text-accent-blue disabled:opacity-50" onClick={onRetry} disabled={offline}>
        {data ? "AI 更新企业清单" : "重新整理企业清单"}
      </button>}
    </div>
    <p className="text-xs text-text-muted">按产业环节列出代表企业，影响力为 AI 研究判断。首次补充或点击更新会调用 AI，再次打开复用记录。</p>
    {loading && <p role="status" className="text-sm text-accent-blue">正在整理代表企业、业务角色与关注理由…{data && "原清单仍可查看。"}</p>}
    {offline && <p role="status" className="text-sm text-text-muted">当前离线，{data ? "保留已保存企业清单。" : "联网后可继续读取。"}</p>}
    {error && <p role="alert" className="text-sm text-accent-red">{error}{data && " 保留上次成功清单与原时间。"}</p>}
    {data && <>
      <p className="text-xs text-text-muted">整理于 {stamp(data.generated_at)}（北京时间） · {data.companies.length} 家企业</p>
      <div className="space-y-4">
        {draft.graph.nodes.map((node) => {
          const companies = data.companies.filter((company) => company.node_id === node.id);
          if (!companies.length) return null;
          return <section key={node.id} aria-label={`${node.label}代表企业`}>
            <h5 className="mb-2 text-sm font-medium text-accent-blue">{node.label}</h5>
            <div className="grid gap-3 xl:grid-cols-2">
              {companies.map((company) => <article key={company.name} className="rounded-md border border-bg-tertiary bg-bg-primary p-3 text-sm">
                <p className="font-semibold">{company.a_share_code
                  ? <Link className="text-accent-blue hover:underline" href={`/stock/${company.a_share_code}`}>{company.name} · {company.a_share_code} ↗</Link>
                  : company.name}</p>
                <p className="mt-2 text-text-secondary">{company.business}</p>
                <p className="mt-2"><span className="font-medium">为何关注：</span>{company.influence}</p>
                {company.reference_status === "ai_candidate" && <p className="mt-2 text-xs text-text-muted">AI 候选 · 业务资料待补充</p>}
                {company.sources.length > 0 && <details className="mt-2 text-xs text-text-muted">
                  <summary className="cursor-pointer text-accent-blue">查看业务资料 · {company.sources.length} 项</summary>
                  {company.sources.map((source) => <div key={source.url} className="mt-3 space-y-1">
                    <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">{source.title} ↗</a>
                    <p>{source.excerpt}</p><p>资料读取于 {stamp(source.accessed_at)}（北京时间），不代表发布日期。</p>
                  </div>)}
                </details>}
              </article>)}
            </div>
          </section>;
        })}
      </div>
      <p className="text-xs text-text-muted">清单用于认识产业参与者，不是市占率排名；列在同一结构中不代表企业之间已存在供货关系。</p>
    </>}
  </section>;
}
