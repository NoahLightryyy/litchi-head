"use client";

import { useEffect, useState } from "react";
import type { AgentAnalysis } from "@/lib/types/debate";
import { HORIZONS, horizonView, horizonConsensus, horizonDistribution, directionLabel, type Horizon } from "@/lib/research-horizon";

export function HorizonResearch({analyses}: {analyses: AgentAnalysis[]}) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 60000); return () => clearInterval(timer); }, []);
  return <section className="space-y-4 mb-4" aria-label="三周期条件研究">
    <h3 className="font-semibold">短、中、长期分别判断</h3>
    <p className="text-sm text-text-muted">研究周期从各流派生成时点起算，报价与财报时间见依据。复核日期不是收益承诺；条件发生变化时应提前复核。系统尚未持续监测这些条件。</p>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {(Object.keys(HORIZONS) as Horizon[]).map(horizon => {
        const distribution = horizonDistribution(analyses, horizon, now);
        return <div key={horizon} className="rounded-lg border border-bg-tertiary bg-bg-primary/50 p-3">
        <p className="font-semibold text-sm">{HORIZONS[horizon]}</p>
        <div className="mt-2 space-y-1 text-sm" aria-label={`${HORIZONS[horizon]}观点分布`}>
          {(["Bullish", "Bearish", "Neutral"] as const).map(direction => <p key={direction}>
            {directionLabel(direction)}：<strong>{distribution.counts[direction]} 个</strong>
            <span className="text-xs text-text-muted">{distribution.total ? `（占全部流派 ${Math.round(distribution.counts[direction] / distribution.total * 100)}%）` : ""}</span>
          </p>)}
          <p className="text-text-muted">未形成有效方向：{distribution.unavailable} 个</p>
        </div>
        <p className="mt-2 text-xs text-text-muted">{horizonConsensus(analyses,horizon,now)}</p>
        <p className="mt-2 text-xs text-text-muted">可用条件观点 {distribution.eligible} / {distribution.total} 个流派</p>
      </div>;
      })}
    </div>
    <p className="text-xs text-text-muted">百分比是有效方向在全部流派中的占比，不是上涨或下跌概率；流派使用相同资料和模型，不能视为独立验证。未形成有效方向包含证据不足、缺项、过期或分析失败，具体原因见下方。</p>
    {(Object.keys(HORIZONS) as Horizon[]).map(horizon => <details key={horizon} open={horizon === "short"} className="rounded-lg border border-bg-tertiary p-4">
      <summary className="cursor-pointer font-semibold">{HORIZONS[horizon]}<span className="block text-sm font-normal text-text-muted mt-1">{horizonConsensus(analyses,horizon,now)}</span></summary>
      <div className="mt-4 space-y-4">{analyses.map((a,index) => {
        const {opinion,eligible,reason} = horizonView(a,horizon,now);
        return <article key={`${a.agent_name}-${index}`} className="rounded-md bg-bg-primary/50 border border-bg-tertiary p-4 space-y-2 text-sm">
          <div className="flex flex-wrap justify-between gap-2"><h4 className="font-semibold">{a.skill_name || a.agent_name}</h4><span>{eligible ? directionLabel(opinion?.direction) : "暂不形成有效方向"}</span></div>
          <p className="text-xs text-text-muted">{reason}</p>
          {opinion && <>
            <p className="whitespace-pre-wrap">{opinion.thesis}</p>
            <p className="text-xs text-text-muted">生成于 {new Date(a.research_generated_at!).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai"})}（北京时间） · 最迟复核 {opinion.review_on}</p>
            <h5 className="font-semibold">成立条件</h5><ul className="list-disc pl-5">{opinion.assumptions.map((x,i)=><li key={i}>{x}</li>)}</ul>
            <h5 className="font-semibold">失效条件</h5><ul className="list-disc pl-5">{opinion.invalidation.map((x,i)=><li key={i}>{x}</li>)}</ul>
            <p><strong>提前复核：</strong>{opinion.review_trigger}</p>
            <h5 className="font-semibold">依据与数据时间</h5><ul className="list-disc pl-5">{opinion.evidence.map((x,i)=><li key={i}>{x}</li>)}</ul>
            <p><strong>限制：</strong>{opinion.limitations}</p>
          </>}
        </article>;
      })}</div>
    </details>)}
  </section>;
}
