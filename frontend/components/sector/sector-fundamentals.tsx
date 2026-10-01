"use client";
import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { fetchFinancials, fetchValuation, fetchIndicators } from "@/lib/api/stocks";
import { FUNDAMENTAL_ROWS, latestFinancial, checkedValuation, displayMetric } from "@/lib/sector-fundamentals";

type Company = {code: string; name: string};
export function SectorFundamentals({members}: {members: Company[]}) {
  const [selected, setSelected] = useState<Company[]>([]);
  const [message, setMessage] = useState("");
  const financials = useQueries({queries: selected.map(({code}) => ({
    queryKey: ["sector-research", code, "financials"], retry: false, staleTime: 300000,
    queryFn: async ({signal}: {signal: AbortSignal}) => latestFinancial(await fetchFinancials(code, AbortSignal.any([signal, AbortSignal.timeout(15000)])), code),
  }))});
  const valuations = useQueries({queries: selected.map(({code}) => ({
    queryKey: ["sector-research", code, "valuation"], retry: false, staleTime: 300000,
    queryFn: async ({signal}: {signal: AbortSignal}) => checkedValuation(await fetchValuation(code, AbortSignal.any([signal, AbortSignal.timeout(15000)])), code),
  }))});
  const industries = useQueries({queries: selected.map(({code}) => ({
    queryKey: ["sector-research", code, "indicators"], retry: false, staleTime: 300000,
    queryFn: ({signal}: {signal: AbortSignal}) => fetchIndicators(code, AbortSignal.any([signal, AbortSignal.timeout(15000)])),
  }))});
  return <section id="fundamentals" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-4" aria-label="板块基本面研究">
    <div><h2 className="font-semibold">基本面研究 · 成分股对比</h2>
      <p className="mt-2 text-sm text-text-muted">从当前页选择最多4家公司，分别查看盈利、成长、现金流、风险与估值。翻页后已选公司仍保留；所选样本不代表整个行业。</p></div>
    <label className="block text-sm">选择成分股
      <select aria-label="选择研究公司" value="" className="mt-2 block w-full rounded border border-bg-tertiary bg-bg-primary p-3" onChange={event => {
        const company = members.find(item => item.code === event.target.value);
        if (!company || selected.some(item => item.code === company.code)) return;
        if (selected.length >= 4) { setMessage("最多对比4家公司，请先移除一项。"); return; }
        setSelected([...selected, company]); setMessage("");
      }}>
        <option value="">选择公司以加载已有财务资料</option>
        {members.map(item => <option key={item.code} value={item.code} disabled={selected.some(s => s.code === item.code)}>{item.name} · {item.code}</option>)}
      </select>
    </label>
    {message && <p role="status" className="text-sm">{message}</p>}
    {!members.length && <p role="status" className="text-sm text-text-muted">成分股尚未取得，请先重试下方成分股列表。</p>}
    {!selected.length ? <p className="text-sm text-text-muted">选中后在这里直接查看，无需离开板块页。</p> : <div className="overflow-x-auto">
      <table className="w-full min-w-[500px] text-sm"><thead><tr><th className="p-3 text-left">维度 / 指标</th>{selected.map(item => <th key={item.code} className="p-3 text-center min-w-44">
        <Link className="text-accent-blue" href={`/stock/${item.code}`}>{item.name}</Link><span className="block text-xs text-text-muted">{item.code}</span>
        <button aria-label={`移除${item.name}`} className="mt-1 text-xs text-text-muted" onClick={() => setSelected(selected.filter(s => s.code !== item.code))}>移除</button>
      </th>)}</tr></thead><tbody>
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">已返回的最新报告期</th>{selected.map((item, i) => <td key={item.code} className="p-3 text-center">
          {financials[i].isPending ? "加载中…" : financials[i].isError ? <button className="text-accent-red" onClick={() => void financials[i].refetch()}>财务加载失败，重试</button> : financials[i].data?.report_date ?? "来源未返回财务"}
        </td>)}</tr>
        {FUNDAMENTAL_ROWS.map(row => <tr key={row.key} className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">{row.label}</th>{selected.map((item, i) => <td key={item.code} className="p-3 text-center font-number">{displayMetric(financials[i].data?.[row.key], row.unit)}</td>)}</tr>)}
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">估值所用报告期</th>{selected.map((item, i) => <td key={item.code} className="p-3 text-center">{valuations[i].isPending ? "加载中…" : valuations[i].isError ? <button className="text-accent-red" onClick={() => void valuations[i].refetch()}>估值加载失败，重试</button> : valuations[i].data?.report_date ?? "未取得可用估值"}</td>)}</tr>
        {(["pe", "pb", "ps"] as const).map(key => <tr key={key} className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">估值 · {key.toUpperCase()}（倍）</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-center font-number">{displayMetric(valuations[i].data?.[key])}</td>)}</tr>)}
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">行业关注指标</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-center text-xs">
          {industries[i].isPending ? "加载中…" : industries[i].isError ? <button className="text-accent-red" onClick={() => void industries[i].refetch()}>行业指标加载失败，重试</button> : industries[i].data?.indicators.length ? <details><summary className="cursor-pointer text-accent-blue">{industries[i].data?.industry} · 指标说明</summary>{industries[i].data?.indicators.map(indicator => <p className="mt-2 text-left" key={indicator.id}>{indicator.name}：{indicator.description}（定义，非实测值）</p>)}</details> : "行业指标尚未取得"}
        </td>)}</tr>
      </tbody></table>
      <button className="mt-3 text-sm text-accent-blue" disabled={[...financials,...valuations,...industries].some(q => q.isFetching)} onClick={() => [...financials,...valuations,...industries].forEach(q => {void q.refetch();})}>刷新研究数据</button>
    </div>}
    <details className="border-t border-bg-tertiary pt-3 text-xs text-text-muted"><summary className="cursor-pointer">资料口径与研究覆盖</summary>
      <p className="mt-2">复用本站个股财务、估值和行业指标接口。报告期为本次来源已返回的最新一期，不保证最新披露已采齐；不同报告期不直接排名。零值可能来自上游缺值，标为待核验；估值行情时点和字段级来源尚未补齐。</p>
      <p className="mt-2">当前没有完整行业AI报告服务。需求、供给、政策与产业链瓶颈仍需专门证据，不能从成分股涨幅推断，也不将这里的财务对比标为AI投资结论。</p>
    </details>
  </section>;
}
