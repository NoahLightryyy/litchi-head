"use client";
import { useQuery } from "@tanstack/react-query";
import { normalizeDataSourceDiagnostics } from "@/lib/backend-health";
export default function DataStatusPage() {
  const query = useQuery({ queryKey: ["source-diagnostics-page"], queryFn: async () => {
    const response = await fetch("/api/health/data-source", { signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error("诊断请求失败");
    const result = normalizeDataSourceDiagnostics(await response.json());
    if (!result) throw new Error("诊断数据格式异常");
    return result;
  }, retry: false, refetchInterval: 30000 });
  return <div className="mx-auto max-w-5xl space-y-4">
    <h1 className="text-2xl font-semibold">数据状态</h1>
    <p className="text-sm text-text-muted">展示后端已记录的数据源调用状态，每30秒更新。调用成功不代表数据完整或已交叉验证；报价日期与覆盖以业务页面为准。</p>
    <button className="rounded bg-accent-blue px-4 py-2 text-white" disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? "正在检查…" : "刷新诊断"}</button>
    {query.isError && <p role="alert" className="text-accent-red">诊断加载失败，已有结果可能过时，请重试。</p>}
    {query.isLoading && <p role="status">正在检查数据源…</p>}
    {query.data && <><p className="text-sm">检查时间：{new Date(query.dataUpdatedAt).toLocaleString("zh-CN")}</p>
      {!Object.keys(query.data.checks).length && <p>暂无已记录的来源调用</p>}
      <div className="grid gap-3 md:grid-cols-2">{Object.entries(query.data.checks).map(([name, check]) => <article key={name} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
        <h2 className="break-all font-semibold">{name}</h2><p className={check.status === "pass" ? "text-accent-blue" : "text-accent-red"}>{check.status === "pass" ? "最近调用成功" : check.status === "warn" ? "返回空数据" : "调用失败"}</p>
        {check.error && <p className="mt-2 text-sm text-text-muted">{check.error}</p>}
      </article>)}</div></>}
  </div>;
}
