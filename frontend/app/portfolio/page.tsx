"use client";
import { useState } from "react";
import { useHoldings } from "@/lib/hooks/use-holdings";
import { portfolioSummary, type Holding } from "@/lib/portfolio";
const blank = { id: "", kind: "stock" as Holding["kind"], code: "", name: "", account: "", sector: "", value: "", cost: "", asOf: "" };
export default function PortfolioPage() {
  const { entries, error, readError, save } = useHoldings();
  const [form, setForm] = useState(blank); const [message, setMessage] = useState("");
  const [removed, setRemoved] = useState<Holding | null>(null);
  const summary = portfolioSummary(entries);
  const money = (value: number) => value.toLocaleString("zh-CN", {minimumFractionDigits:2, maximumFractionDigits:2});
  return <div className="mx-auto max-w-6xl space-y-5">
    <h1 className="text-2xl font-semibold">持仓与风险</h1>
    <p className="text-sm text-text-muted">手动记录人民币股票与基金持仓，金额以你填写的日期为准。数据仅保存在本浏览器，不连接同花顺或支付宝账户。</p>
    {error && <p role="alert" className="text-accent-red">{error}</p>}
    <form className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 space-y-3" onSubmit={(e) => {
      e.preventDefault();
      const values = new FormData(e.currentTarget);
      const item: Holding = { ...form, asOf: String(values.get("asOf") ?? ""), id: form.id || crypto.randomUUID(), value: Number(form.value), cost: form.cost === "" ? null : Number(form.cost) };
      if (save([...entries.filter((entry) => entry.id !== item.id), item])) { setForm(blank); setMessage("持仓记录已保存"); }
    }}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm">资产类型<select value={form.kind} onChange={(e) => setForm({...form,kind:e.target.value as Holding["kind"]})} className="block w-full rounded border border-bg-tertiary bg-bg-primary p-2"><option value="stock">股票</option><option value="fund">基金</option></select></label>
        {([['code','代码'],['name','名称'],['account','账户标签（可选）'],['sector','行业/主题（可选，自填）'],['value','当前持仓金额（元）'],['cost','持仓总成本（元，可选）'],['asOf','金额对应日期']] as const).map(([key,label]) => <label key={key} className="text-sm">{label}<input
          name={key} required={['code','name','value','asOf'].includes(key)} type={key === 'asOf' ? 'date' : ['value','cost'].includes(key) ? 'number' : 'text'}
          min={['value','cost'].includes(key) ? 0 : undefined} step={['value','cost'].includes(key) ? '0.01' : undefined}
          pattern={key === 'code' ? '[0-9]{6}' : undefined} maxLength={key === 'code' ? 6 : 100}
          value={form[key]} onChange={(e) => setForm({...form,[key]:e.target.value})} className="block w-full rounded border border-bg-tertiary bg-bg-primary p-2" /></label>)}
      </div>
      <button disabled={!!readError} className="rounded bg-accent-blue px-4 py-2 text-white disabled:opacity-40">{form.id ? "保存修改" : "添加持仓"}</button>
      {form.id && <button type="button" className="ml-3 text-sm" onClick={() => setForm(blank)}>取消编辑</button>}
      <p role="status">{message}</p>
    </form>
    {removed && <p role="status" className="text-sm">已移除 {removed.name} <button className="text-accent-blue" onClick={() => { if (save([...entries, removed])) setRemoved(null); }}>撤销移除</button></p>}
    {!entries.length ? <p className="p-6 text-center text-text-muted">尚未录入持仓，录入后显示金额分布与集中度。</p> : <>
      <div className="grid gap-3 sm:grid-cols-3">{[["已录入持仓合计", money(summary.total)+" 元"],["最大单项占比",summary.largestWeight === null ? "无法计算" : (summary.largestWeight*100).toFixed(1)+"%"],["账面差额（金额−成本）",summary.costComplete ? money(summary.total-summary.cost)+" 元" : "成本不完整，暂不计算"]].map(([label,value]) => <div key={label} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4"><p className="text-xs text-text-muted">{label}</p><p className="mt-2 text-xl font-number">{value}</p></div>)}</div>
      <p className="text-sm text-text-muted">占比仅针对已录入持仓，不含未录入现金或资产；账面差额不含历史卖出、分红和费用。不同日期金额合计只作记录汇总。基金未穿透底层持仓，无法据此判断与股票是否重叠。</p>
      <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4"><h2 className="font-semibold mb-3">自填行业 / 主题分布</h2>{summary.groups.map(([name,value]) => <div key={name} className="mb-3"><div className="flex justify-between text-sm"><span>{name}</span><span>{money(value)} 元 · {summary.total > 0 ? (value/summary.total*100).toFixed(1)+"%" : "—"}</span></div><div className="h-2 mt-1 rounded bg-bg-tertiary"><div className="h-full rounded bg-accent-blue" style={{width:summary.total > 0 ? `${value/summary.total*100}%` : '0%'}} /></div></div>)}</section>
      <div className="overflow-auto"><table className="w-full min-w-[650px] text-sm"><thead><tr>{['资产','账户','行业/主题','金额（元）','日期','操作'].map((x)=><th key={x} className="text-left p-3">{x}</th>)}</tr></thead><tbody>{entries.map((entry)=><tr key={entry.id} className="border-t border-bg-tertiary"><td className="p-3">{entry.name} · {entry.code}<p className="text-xs text-text-muted">{entry.kind === 'stock' ? '股票' : '基金'}</p></td><td className="p-3">{entry.account || '未填写'}</td><td className="p-3">{entry.sector || '未分类'}</td><td className="p-3">{money(entry.value)}</td><td className="p-3">{entry.asOf}</td><td className="p-3"><button className="text-accent-blue" onClick={()=>setForm({...entry,value:String(entry.value),cost:entry.cost === null ? '' : String(entry.cost)})}>编辑</button><button className="ml-3 text-text-muted" onClick={() => { if (save(entries.filter((item) => item.id !== entry.id))) setRemoved(entry); }}>移除</button></td></tr>)}</tbody></table></div>
    </>}
  </div>;
}
