import type { AgentAnalysis } from "../../lib/types/debate";

/** Render only returned research; failed agents never become neutral recommendations. */
export function AgentAnalysisList({ analyses }: { analyses: AgentAnalysis[] }) {
  const completed = analyses.filter((a) => a.success === true);
  const failed = analyses.filter((a) => a.success !== true);
  return <section className="space-y-4" aria-label="各流派分析">
    <div>
      <h3 className="font-semibold">各流派分析</h3>
      <p className="mt-1 text-xs text-text-muted">已返回 {completed.length} 个 · 未完成 {failed.length} 个。分别查看研究依据，评分不等于收益预测。</p>
    </div>
    {!analyses.length && <p className="text-sm text-text-muted">本次尚未返回任何流派分析。</p>}
    {completed.map((a, i) => <article key={`${a.agent_name}-${i}`} className="rounded-lg border border-bg-tertiary bg-bg-primary/50 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold">{a.skill_name || a.agent_name}</h4>
        <span className="text-sm text-text-secondary">{a.direction === "Bullish" ? "看涨" : a.direction === "Bearish" ? "看跌" : a.direction === "Neutral" ? "中性" : "方向未提供"}</span>
      </div>
      <p className="text-sm leading-6 whitespace-pre-wrap break-words">{a.summary?.trim() || "本流派未提供摘要。"}</p>
      <details className="group rounded border border-bg-tertiary p-3">
        <summary className="cursor-pointer text-sm text-accent-blue">完整分析与依据</summary>
        <div className="mt-3 space-y-4 text-sm leading-6 break-words">
          <div><h5 className="font-semibold">分析论证</h5><p className="whitespace-pre-wrap">{a.analysis?.trim() || "本流派未返回完整论证。"}</p></div>
          <div><h5 className="font-semibold">关键依据</h5>{a.key_evidence?.length ? <ul className="list-disc pl-5">{a.key_evidence.map((e, j) => <li key={j} className="whitespace-pre-wrap">{e}</li>)}</ul> : <p className="text-text-muted">未提供独立列出的依据。</p>}</div>
          <div><h5 className="font-semibold">风险与限制</h5><p className="whitespace-pre-wrap">{a.risk_warning?.trim() || "本流派未提供风险说明，不代表没有风险。"}</p></div>
          <p className="text-xs text-text-muted">以上为模型返回的研究内容；依据文本不自动等同于已核验来源。</p>
        </div>
      </details>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-text-muted">
        <span>原始评分：{Number.isFinite(a.score) && a.score >= 0 && a.score <= 100 ? `${a.score}/100` : "未提供"}</span>
        <span>模型置信度：{Number.isFinite(a.confidence) && a.confidence >= 0 && a.confidence <= 1 ? `${(a.confidence * 100).toFixed(0)}%` : "未提供"}（非胜率）</span>
        <span>{a.agent_name}</span>
      </div>
    </article>)}
    {failed.length > 0 && <div className="rounded-lg border border-accent-gold/30 p-4">
      <h4 className="font-semibold">未完成的流派</h4>
      <p className="mt-1 text-xs text-text-muted">下列流派没有可用结论，不按中性或零分参与展示。</p>
      <ul className="mt-2 space-y-2 text-sm">{failed.map((a, i) => <li key={`${a.agent_name}-${i}`} className="flex flex-wrap justify-between gap-2"><span>{a.skill_name || a.agent_name}</span><span className="text-text-muted">分析未成功</span></li>)}</ul>
    </div>}
  </section>;
}
