"use client";
import { useTechnicalSupplement } from "@/lib/hooks/use-technical-supplement";
import { TechnicalSupplementView } from "./technical-supplement-view";

export function TechnicalSupplementPanel({ stockCode }: { stockCode: string }) {
  const query = useTechnicalSupplement(stockCode);
  return <section className="mb-5 rounded-xl border border-accent-blue/30 bg-bg-secondary p-4 sm:p-5 space-y-3" aria-label="复权与成交量补充">
    <div className="flex flex-wrap justify-between gap-2 items-center">
      <h3 className="font-semibold">复权与成交量补充</h3>
      <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching}
        className="text-sm text-accent-blue disabled:opacity-50">{query.isFetching ? "读取中…" : "重新读取（不调用AI）"}</button>
    </div>
    {query.isPending && <p role="status" className="text-sm text-text-muted">正在读取前复权日线和成交量，不影响查看已有研究…</p>}
    {query.isError && <p role="status" className="text-sm text-text-secondary">本次补充资料未读取成功。{query.data ? "保留上次资料，请留意所示日期。" : "可稍后重新读取；已有研究仍可查看。"}</p>}
    {query.data && query.data.stock_code === stockCode && <TechnicalSupplementView data={query.data} />}
  </section>;
}
