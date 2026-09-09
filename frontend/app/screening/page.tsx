"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { fetchFinancials, fetchValuation } from "@/lib/api/stocks";
import { useStockSearch } from "@/lib/hooks/use-stock";
import { useResearchList } from "@/lib/hooks/use-research-list";
export default function ScreeningPage() { return <Suspense fallback={<p>正在加载选股区…</p>}><Screening /></Suspense>; }
function Screening() {
  const params = useSearchParams();
  const initial = params.get("code") ?? "";
  const [codes, setCodes] = useState<string[]>(/^\d{6}$/.test(initial) ? [initial] : []);
  const [input, setInput] = useState("");
  const [message, setMessage] = useState("");
  const { entries } = useResearchList();
  const search = useStockSearch(input);
  function add(code: string) {
    if (!/^\d{6}$/.test(code)) { setMessage("请输入6位股票代码，或从搜索结果选择。"); return; }
    if (codes.includes(code)) { setMessage("已在对比中"); return; }
    if (codes.length >= 4) { setMessage("每次最多比较4家公司，请先移除一项。"); return; }
    setCodes([...codes, code]); setMessage(""); setInput("");
  }
  const financials = useQueries({ queries: codes.map((code) => ({ queryKey: ["stocks", code, "financials"], queryFn: ({ signal }: { signal: AbortSignal }) => fetchFinancials(code, AbortSignal.any([signal, AbortSignal.timeout(15000)])), retry: false, staleTime: 300000 })) });
  const valuations = useQueries({ queries: codes.map((code) => ({ queryKey: ["stocks", code, "valuation"], queryFn: ({ signal }: { signal: AbortSignal }) => fetchValuation(code, AbortSignal.any([signal, AbortSignal.timeout(15000)])), retry: false, staleTime: 300000 })) });
  const metrics = [
    { label: "盈利 · ROE (%)", key: "roe" as const },
    { label: "盈利 · 毛利率 (%)", key: "gross_margin" as const },
    { label: "现金流 · 每股经营现金流 (元)", key: "operating_cf_per_share" as const },
    { label: "成长 · 营收增长 (%)", key: "revenue_growth" as const },
    { label: "成长 · 净利润增长 (%)", key: "net_profit_growth" as const },
    { label: "风险 · 资产负债率 (%)", key: "debt_ratio" as const },
  ];
  const format = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value === 0 ? "0.00（待核验）" : value.toFixed(2) : "未知";
  return <div className="mx-auto max-w-7xl space-y-5">
    <h1 className="text-2xl font-semibold">选股与对比</h1>
    <p className="text-sm text-text-muted">按代码或名称加入公司，分别比较盈利、成长、财务风险与估值。不同报告期和行业指标不可直接等同；本表不生成综合评级。</p>
    <p className="rounded border border-bg-tertiary p-3 text-sm text-text-muted">当前为既有接口的原始指标对照：报告期可能较早，尚不能确认是最新披露；零值无法区分真实为零与上游缺值，已标为待核验。估值行情时点与公司产业映射尚未补齐。</p>
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); add(input.trim()); }}>
      <input aria-label="搜索对比股票" value={input} onChange={(e) => setInput(e.target.value)} placeholder="股票名称或6位代码" className="min-w-0 flex-1 rounded border border-bg-tertiary bg-bg-secondary p-3" />
      <button className="rounded bg-accent-blue px-4 text-white">加入对比</button>
    </form>
    {message && <p role="status">{message}</p>}
    {search.isError && input.length >= 2 && <p role="alert">搜索暂不可用，可输入已知股票代码。</p>}
    {input.length >= 2 && search.data && <div className="flex flex-wrap gap-2">{search.data.filter((item) => item.type === "stock").slice(0, 8).map((item) => <button key={item.code} onClick={() => add(item.code)} className="rounded border border-bg-tertiary p-2 text-sm">{item.name} · {item.code}</button>)}</div>}
    {entries.length > 0 && <div className="flex flex-wrap gap-2"><span className="text-sm text-text-muted">从自选加入</span>{entries.slice(0, 20).map((item) => <button key={item.code} onClick={() => add(item.code)} className="text-sm text-accent-blue">{item.name}</button>)}</div>}
    {!codes.length ? <p className="rounded-lg border border-bg-tertiary bg-bg-secondary p-8 text-center">加入公司后展示并列指标；也可先到行业研究中筛选板块。</p> : <div className="overflow-x-auto rounded-lg border border-bg-tertiary bg-bg-secondary">
      <table className="w-full min-w-[600px] text-sm"><thead><tr><th className="p-3 text-left">维度 / 指标</th>{codes.map((code) => <th key={code} className="p-3"><Link href={`/stock/${code}`} className="text-accent-blue">{entries.find((entry) => entry.code === code)?.name ?? code}</Link><button aria-label={`移除对比${code}`} className="ml-3 text-text-muted" onClick={() => setCodes(codes.filter((item) => item !== code))}>×</button></th>)}</tr></thead>
      <tbody>
        <tr><th className="p-3 text-left">财务报告期 / 状态</th>{codes.map((code, index) => <td key={code} className="p-3 text-center">{financials[index].isPending ? "加载中…" : financials[index].isError ? <button className="text-accent-red" onClick={() => void financials[index].refetch()}>加载失败，重试</button> : financials[index].data?.[0]?.report_date ?? "暂无财务数据"}</td>)}</tr>
        {metrics.map((metric) => <tr key={metric.key} className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">{metric.label}</th>{codes.map((code, index) => <td key={code} className="p-3 text-center font-number">{format(financials[index].data?.[0]?.[metric.key])}</td>)}</tr>)}
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left">估值依据报告期 / 状态</th>{codes.map((code, index) => <td key={code} className="p-3 text-center">{valuations[index].isPending ? "加载中…" : valuations[index].isError ? <button className="text-accent-red" onClick={() => void valuations[index].refetch()}>加载失败，重试</button> : valuations[index].data?.report_date ?? "暂无估值数据"}</td>)}</tr>
        {(["pe", "pb", "ps"] as const).map((key) => <tr key={key} className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">估值 · {key.toUpperCase()} (倍)</th>{codes.map((code, index) => <td key={code} className="p-3 text-center font-number">{format(valuations[index].data?.[key])}</td>)}</tr>)}
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left">产业位置 / 业务证据</th>{codes.map((code) => <td key={code} className="p-3 text-center text-text-muted">尚未接入可核验公司映射</td>)}</tr>
      </tbody></table>
    </div>}
    <details className="rounded-lg border border-bg-tertiary p-4 text-sm text-text-muted"><summary className="cursor-pointer">指标说明与数据限制</summary><p className="mt-2">ROE衡量净资产回报，毛利率衡量毛利占营收比例；每股经营现金流观察现金兑现。营收/利润增长反映变化，资产负债率仅是风险的一部分。PE/PB/PS分别对应盈利、净资产和收入的估值倍数，负值或不适用行业不作高低排名。</p><p className="mt-2">复用既有财务与估值接口；估值由财报和行情计算，当前接口未完整提供行情时点及原始来源链路。零值也可能受上游缺值处理影响，因此仅供核对原始指标，不自动作优劣筛选。完整来源、行业可比口径和多维筛选仍待研究契约补齐。</p></details>
    <Link href="/industries" className="text-accent-blue">前往行业研究筛选板块</Link>
  </div>;
}
