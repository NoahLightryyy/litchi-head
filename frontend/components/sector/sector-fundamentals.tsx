"use client";
import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { fetchIndicators } from "@/lib/api/stocks";
import { api } from "@/lib/api/client";
import { FUNDAMENTAL_ROWS, checkedResearch, displayMetric, publicationDate } from "@/lib/sector-fundamentals";

type Company = {code: string; name: string};
export function SectorFundamentals({members, membersLoading = false}: {members: Company[]; membersLoading?: boolean}) {
  const [selected, setSelected] = useState<Company[]>([]);
  const [message, setMessage] = useState("");
  const financials = useQueries({queries: selected.map(({code}) => ({
    queryKey: ["sector-research", code, "statements-v1"], retry: false, staleTime: 60000,
    queryFn: async ({signal}: {signal: AbortSignal}) => checkedResearch(await api.getRaw(`/stocks/${code}/fundamental-research`, undefined,
      {signal: AbortSignal.any([signal, AbortSignal.timeout(15000)])}), code),
  }))});
  const industries = useQueries({queries: selected.map(({code}) => ({
    queryKey: ["sector-research", code, "indicators"], retry: false, staleTime: 300000,
    queryFn: ({signal}: {signal: AbortSignal}) => fetchIndicators(code, AbortSignal.any([signal, AbortSignal.timeout(15000)])),
  }))});
  return <section id="fundamentals" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-4" aria-label="板块基本面研究">
    <div><h2 className="font-semibold">基本面研究 · 成分股对比</h2>
      <p className="mt-2 text-sm text-text-muted">从当前页选择最多4家公司，分别查看盈利、成长、现金流、风险与估值。翻页后已选公司仍保留；所选样本不代表整个行业。</p></div>
    <label className="block text-sm">选择成分股
      <select aria-label="选择研究公司" disabled={membersLoading} value="" className="mt-2 block w-full rounded border border-bg-tertiary bg-bg-primary p-3" onChange={event => {
        const company = members.find(item => item.code === event.target.value);
        if (!company || selected.some(item => item.code === company.code)) return;
        if (selected.length >= 4) { setMessage("最多对比4家公司，请先移除一项。"); return; }
        setSelected([...selected, company]); setMessage("");
      }}>
        <option value="">选择公司以加载合并财报</option>
        {members.map(item => <option key={item.code} value={item.code} disabled={selected.some(s => s.code === item.code)}>{item.name} · {item.code}</option>)}
      </select>
    </label>
    {message && <p role="status" className="text-sm">{message}</p>}
    {!members.length && <p role="status" className="text-sm text-text-muted">{membersLoading ? "正在加载当前页成分股…" : "成分股尚未取得，请先重试下方成分股列表。"}</p>}
    {!selected.length ? <p className="text-sm text-text-muted">选中后在这里直接查看，无需离开板块页。</p> : <div className="overflow-x-auto">
      <table className="w-full min-w-[500px] text-sm"><thead><tr><th className="p-3 text-left">维度 / 指标</th>{selected.map(item => <th key={item.code} className="p-3 text-center min-w-44">
        <Link className="text-accent-blue" href={`/stock/${item.code}`}>{item.name}</Link><span className="block text-xs text-text-muted">{item.code}</span>
        <button aria-label={`移除${item.name}`} className="mt-1 text-xs text-text-muted" onClick={() => setSelected(selected.filter(s => s.code !== item.code))}>移除</button>
      </th>)}</tr></thead><tbody>
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">已返回的最新报告期</th>{selected.map((item, i) => <td key={item.code} className="p-3 text-center">
          {financials[i].isPending ? "加载中…" : financials[i].isError ? <button className="text-accent-red" onClick={() => void financials[i].refetch()}>财务加载失败，重试</button> : financials[i].data?.report_date ?? "来源未返回财务"}
        </td>)}</tr>
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">来源所示披露日</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-center">{publicationDate(financials[i].data)}</td>)}</tr>
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">资料状态</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-center text-xs">
          {financials[i].data?.status === "stale" ? "更新失败 · 显示旧快照" : financials[i].data?.status === "unavailable" ? "报表暂未取得" : financials[i].data ? "财务单源 · 估值条件待补" : "—"}
        </td>)}</tr>
        {FUNDAMENTAL_ROWS.map(row => <tr key={row.key} className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">{row.label}</th>{selected.map((item, i) => <td key={item.code} className="p-3 text-center font-number" title={financials[i].data?.metrics[row.key]?.reason ?? financials[i].data?.metrics[row.key]?.basis}>{displayMetric(financials[i].data?.metrics[row.key])}</td>)}</tr>)}
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">估值缺少条件</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-xs text-text-muted">{financials[i].data?.metrics.pe?.reason ?? "—"}</td>)}</tr>
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">计算口径与来源</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-xs">
          {financials[i].data && <details><summary className="cursor-pointer text-accent-blue">查看报表、公式与缺值原因</summary>
            <p className="mt-3">采集时间：{financials[i].data?.fetched_at ? new Date(financials[i].data!.fetched_at!).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai"}) : "—"}（北京时间）</p>
            {financials[i].data?.warnings.map((warning,j) => <p key={j} className="mt-2">{warning}</p>)}
            {financials[i].data?.statements.map(s => <p key={`${s.kind}-${s.report_date}`} className="mt-3"><a className="text-accent-blue" href={s.source_url} target="_blank" rel="noopener noreferrer">{({lrb:"利润表",fzb:"资产负债表",llb:"现金流量表"})[s.kind]} · {s.report_date} ↗</a><br/>来源披露日 {s.published_at ?? "未提供"} · 人民币合并报表</p>)}
            {FUNDAMENTAL_ROWS.map(row => <p key={row.key} className="mt-3">{row.label}：{financials[i].data?.metrics[row.key]?.basis ?? "未取得"}{financials[i].data?.metrics[row.key]?.reason && `；${financials[i].data?.metrics[row.key]?.reason}`}</p>)}
          </details>}
        </td>)}</tr>
        <tr className="border-t border-bg-tertiary"><th className="p-3 text-left font-normal">行业关注指标</th>{selected.map((item,i) => <td key={item.code} className="p-3 text-center text-xs">
          {industries[i].isPending ? "加载中…" : industries[i].isError ? <button className="text-accent-red" onClick={() => void industries[i].refetch()}>行业指标加载失败，重试</button> : industries[i].data?.indicators.length ? <details><summary className="cursor-pointer text-accent-blue">{industries[i].data?.industry} · 指标说明</summary>{industries[i].data?.indicators.map(indicator => <p className="mt-2 text-left" key={indicator.id}>{indicator.name}：{indicator.description}（定义，非实测值）</p>)}</details> : "行业指标尚未取得"}
        </td>)}</tr>
      </tbody></table>
      <button className="mt-3 text-sm text-accent-blue" disabled={[...financials,...industries].some(q => q.isFetching)} onClick={() => [...financials,...industries].forEach(q => {void q.refetch();})}>刷新研究数据</button>
    </div>}
    <details className="border-t border-bg-tertiary pt-3 text-xs text-text-muted"><summary className="cursor-pointer">资料口径与研究覆盖</summary>
      <p className="mt-2">财务来自新浪合并报表，报告期为来源返回的最新一期，不保证最新披露已采齐。披露日是来源记录，采集时间另列。金额统一显示亿元；收入、利润、现金流为年内累计，TTM为滚动十二个月。缺值显示—，真实零与负数保留；不同报告期不直接排名。期末权益回报率并非加权平均ROE。</p>
      <p className="mt-2">当前没有完整行业AI报告服务。需求、供给、政策与产业链瓶颈仍需专门证据，不能从成分股涨幅推断，也不将这里的财务对比标为AI投资结论。</p>
    </details>
  </section>;
}
