import { noResearchMessage, type AnalysisOutcome } from "../../lib/debate-failure.ts";

export function DebateFailureNotice({ analyses }: { analyses: AnalysisOutcome[] }) {
  return <section role="alert" className="mb-4 rounded-md border border-accent-red/30 bg-accent-red/10 p-4 space-y-2">
    <h3 className="font-semibold">本次 AI 分析未生成成功</h3>
    <p className="text-sm leading-6">{noResearchMessage(analyses)}</p>
    <p className="text-xs text-text-muted">没有有效分析，因此不展示方向统计或生成入场计划。已保存的其他研究不受影响，可在分析历史中查看。</p>
  </section>;
}
