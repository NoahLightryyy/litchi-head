"use client";
import {useState} from "react";
import {capitalScenario} from "@/lib/capital-scenarios";
const money = (n:number) => n.toLocaleString("zh-CN",{maximumFractionDigits:2});
export function CapitalComparison() {
  const [apiFee,setApiFee]=useState("120");
  const [trades,setTrades]=useState("10");
  const valid=apiFee.trim()!=="" && trades.trim()!=="" && Number.isFinite(Number(apiFee)) && Number(apiFee)>=0 && Number(apiFee)<=1e6 && Number.isInteger(Number(trades)) && Number(trades)>=0 && Number(trades)<=1000;
  const rows=valid ? [10000,100000,500000].map(c=>capitalScenario(c,Number(apiFee),Number(trades))) : [];
  return <div className="mx-auto max-w-6xl space-y-6">
    <header><p className="text-sm text-accent-blue">策略实验室 · 假设情景</p><h3 className="text-2xl font-semibold mt-2">不同本金，怎样执行同一份研究？</h3><p className="mt-3 text-text-secondary">比较1万、10万和50万元的执行约束与成本。不是你的账户配置，也没有预测收益。</p></header>
    <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-3">
      <h2 className="font-semibold">先固定风险条件，再比较本金</h2><p className="text-sm text-text-secondary">生活和应急资金已另行保留，无近期必需用款，期限3年，不使用杠杆。试算结构：权益核心60%、主题研究额度20%、现金20%。主题额度未经证据验证时保持现金。</p>
      <div className="flex flex-wrap gap-5"><label className="text-sm">每月API研究费（元）<input className="block mt-2 rounded border border-bg-tertiary bg-bg-primary p-2" type="number" min="0" max="1000000" value={apiFee} onChange={e=>setApiFee(e.target.value)}/></label><label className="text-sm">每月完整买卖次数<input className="block mt-2 rounded border border-bg-tertiary bg-bg-primary p-2" type="number" min="0" max="1000" step="1" value={trades} onChange={e=>setTrades(e.target.value)}/></label></div>
      <p className="text-xs text-text-muted">费用假设：每笔成交金额为本金10%，单边佣金0.03%、最低5元。不含税费、点差与滑点，不是券商实际报价。</p>
      {!valid && <p role="alert">研究费请输入0至1,000,000元，买卖次数请输入0至1,000的整数。</p>}
    </section>
    {valid && <section aria-label="本金情景对照" className="overflow-x-auto rounded-lg border border-bg-tertiary bg-bg-secondary p-4"><table className="w-full text-sm text-left"><caption className="text-left font-semibold pb-4">相同假设下的金额与压力对照 · 人民币</caption><thead><tr><th className="p-3">比较项目</th>{rows.map(r=><th key={r.capital} className="p-3 whitespace-nowrap">{money(r.capital)}元</th>)}</tr></thead><tbody>
      {([['权益核心', (r:ReturnType<typeof capitalScenario>)=>money(r.core)+'元'],['主题研究额度（未验证时留现金）',r=>money(r.theme)+'元'],['现金',r=>money(r.cash)+'元'],['压力损失（19%）',r=>money(r.loss)+'元'],['主题未投入时压力损失（12%）',r=>money(r.uninvestedLoss)+'元'],['每月佣金算例',r=>money(r.commission)+'元'],['每月佣金＋研究费',r=>money(r.monthlyCost)+'元'],['月成本占本金',r=>r.monthlyCostPct.toFixed(3)+'%'],['假设最低买入3,000元占本金',r=>r.minimumOrderPct.toFixed(1)+'%'],['该买入是否超出主题额度',r=>r.themeExecutable?'未超额度，仍需核验证据':'超额度，不可执行']] as [string,(r:ReturnType<typeof capitalScenario>)=>string][]).map(([label,render])=><tr key={label} className="border-t border-bg-tertiary"><th className="p-3 font-normal">{label}</th>{rows.map(r=><td className="p-3 font-number" key={r.capital}>{render(r)}</td>)}</tr>)}
    </tbody></table><p className="text-xs text-text-muted mt-4">压力假设为核心下跌20%、主题下跌35%、现金不变；不是最坏损失或止损保证。最低买入假设为30元×100单位，具体证券规则需另行核验。</p></section>}
    <section className="grid gap-4 md:grid-cols-3">{[['1万元：控制固定成本','检验少量分散工具与按需研究，避免小额频繁交易被最低佣金侵蚀。'],['10万元：核验研究增益','检查跨工具持仓重合，按证据选择候选，评估再平衡的必要性。'],['50万元：看组合与现金','关注相关暴露、绝对损失和流动性，不因本金增加自动提高风险。']].map(([title,body])=><article key={title} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5"><h2 className="font-semibold">{title}</h2><p className="text-sm text-text-secondary mt-3">{body}</p></article>)}</section>
    <p className="text-sm text-text-secondary">实际方案还需用钱期限、负债、可承受绝对损失、持仓和交易权限。当前 AI政策研究样例 尚无公司级兑现证据，三种本金的主题额度均先保持未投入。</p>
  </div>;
}
