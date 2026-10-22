export function PolicySample() {
  return <div className="mx-auto max-w-6xl space-y-6">
    <header><p className="text-sm text-accent-blue">政策与国家战略 · 历史样例</p><h3 className="mt-2 text-2xl font-semibold">人工智能＋：从政策方向到商业兑现</h3><p className="mt-3 text-text-secondary">央视报道提供研究线索，政策原文确认事实；企业能否获得订单与回款，需要继续核验。</p></header>
    <div className="rounded-lg border border-accent-gold/30 bg-accent-gold/10 p-4 text-sm">2025年报道演示 · 整理于2026-10-18。不是当日新闻，不代表已接入实时央视新闻流。以下解读由本产品整理，不代表央视观点。</div>
    <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-3"><h2 className="font-semibold">本次研究结论：先观察，暂不形成买入判断</h2><p>政策方向已明确，公司级付费订单、利润和现金流证据尚待补充。应用普及目标不等于企业收入增速，更不等于股票收益。</p></section>
    <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-3"><h2 className="font-semibold">来源事实</h2><p className="text-sm">央视网《从实验室到千行百业：我国“人工智能+”六大行动全景图出炉》，报道时间2025-08-27 11:03:56。</p><p className="text-sm">国务院国发〔2025〕11号，成文2025-08-21。央视记载对外发布为8月26日，官方转载页面日期为8月27日。</p><p className="text-sm">政策设定2027年、2030年新一代智能终端、智能体等应用普及率超过70%、90%的目标；这两项是政策目标。</p><div className="flex flex-wrap gap-4 text-sm text-accent-blue"><a href="https://news.cctv.cn/2025/08/27/ARTIj8A653Df44jjD41hdRqP250827.shtml" target="_blank" rel="noopener noreferrer" className="underline">央视报道 ↗</a><a href="https://www.mee.gov.cn/zcwj/gwywj/202508/t20250827_1126207.shtml" target="_blank" rel="noopener noreferrer" className="underline">国务院文件官方转载 ↗</a></div></section>
    <section className="space-y-3"><h2 className="font-semibold">传导假设 · 点击展开核验与反证</h2>{[
      ['工业软件与智能制造','应用推广可能带来软件、设备和实施服务需求。','有金额与交付条件的合同、客户验收、复购、收入确认。','只有试点演示，客户不付费，实施成本吞噬利润。'],
      ['算力与服务','应用增长可能增加算力需求，效率提升也可能减少单位需求。','利用率、服务单价、付费调用量、资本开支与经营现金流。','利用率不足、价格下降快于成本下降、投入难以回收。'],
      ['AI终端','新功能可能促进换机，也可能只是营销标签。','实际销量、活跃使用、价格溢价和单位毛利。','出货增长但功能无人用，价格战或退货抵消增量。']
    ].map(([title,hypothesis,evidence,counter])=><details key={title} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5"><summary className="cursor-pointer font-semibold">{title}</summary><div className="mt-4 space-y-3 text-sm"><p><strong>产品推断：</strong>{hypothesis}</p><p><strong>待补证据：</strong>{evidence}</p><p><strong>反证条件：</strong>{counter}</p><p className="text-text-muted">尚未核验公司披露，不生成确定性受益公司名单。</p></div></details>)}</section>
    <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5"><h2 className="font-semibold">跟踪安排样例</h2><ol className="list-decimal pl-5 mt-3 space-y-2 text-sm"><li>30天：检查具体实施文件或采购安排。</li><li>90天：检查付费项目、交付与复购。</li><li>180天：检查收入、毛利和现金流。</li></ol><p className="text-xs text-text-muted mt-4">以上从实际开始观察之日计时，当前未创建自动跟踪任务。期限是研究安排，不是兑现承诺。历史样例不能倒填成事前预测。</p></section>
  </div>;
}
