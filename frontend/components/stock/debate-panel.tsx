"use client";

import { useState } from "react";
import { MessageSquare, RefreshCw } from "lucide-react";
import { useRunDebate, useDebateResult, useDebateHistory } from "@/lib/hooks/use-debate";
import type { AgentAnalysis, VoteSummary } from "@/lib/types/debate";
import { debateErrorMessage } from "@/lib/debate-error";
import { HorizonResearch } from "./horizon-research";
import { AgentAnalysisList } from "./agent-analysis-list";
import { DEBATE_FAILURE_MESSAGE, DEBATE_TIMEOUT_MESSAGE } from "@/lib/debate-session";
import { selectDebateView } from "@/lib/debate-history";
import { debateLimitations } from "@/lib/debate-limitations";

interface DebatePanelProps {
  stockCode: string;
  stockName: string;
}

/** AI 辩论面板：触发辩论 → 后端真实调用 → 展示大师分析 → 共识汇总 */
export function DebatePanel({ stockCode, stockName }: DebatePanelProps) {
  const { trigger, sessionId, running } = useRunDebate();
  const [error, setError] = useState<string | null>(null);
  const [triggered, setTriggered] = useState(false);

  const [selectedHistory, setSelectedHistory] = useState<string | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const history = useDebateHistory(stockCode, historyOffset);
  const records = (history.data ?? []).filter((item) => item.stock_code === stockCode);
  const {sessionId: effectiveSessionId, historical: viewingHistory} = selectDebateView(
    records, stockCode, selectedHistory, sessionId, triggered,
  );
  const { data: debateResult, isError: resultQueryFailed, isTimedOut } = useDebateResult(effectiveSessionId);
  const selectedRecord = records.find((item) => item.session_id === effectiveSessionId);
  const hasActiveRecord = records.some((item) => item.status === "running" || item.status === "queued");

  const handleDebate = async () => {
    setError(null);
    setSelectedHistory(null);
    setHistoryOffset(0);
    setTriggered(true);
    try {
      await trigger({ stock_code: stockCode, question: `${stockName} 投资分析` });
    } catch (cause) {
      setError(debateErrorMessage(cause));
    } finally {
      void history.refetch();
    }
  };

  const resultIdentityMismatch = Boolean(
    effectiveSessionId && debateResult && (debateResult.session_id !== effectiveSessionId
      || debateResult.stock_code !== stockCode),
  );
  const resultFailed = resultQueryFailed || resultIdentityMismatch;
  const visibleError = (viewingHistory ? null : error)
    ?? (isTimedOut ? DEBATE_TIMEOUT_MESSAGE : null)
    ?? (resultFailed ? DEBATE_FAILURE_MESSAGE : null);
  const awaitingResult = Boolean(
    effectiveSessionId && !debateResult?.vote_summary && !resultFailed && !isTimedOut,
  );
  const isRunning = (!viewingHistory && running) || awaitingResult;
  const results = !visibleError && (!running || viewingHistory) && effectiveSessionId
    && debateResult?.stock_code === stockCode
    && debateResult?.session_id === effectiveSessionId && debateResult.vote_summary
    ? {
        voteSummary: debateResult.vote_summary as VoteSummary,
        analyses: (debateResult.analyses ?? []) as AgentAnalysis[],
      }
    : null;

  const limitations = debateLimitations(debateResult);

  return (
    <div>
      {/* 头部 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">各流派分析与辩论</h3>
          <p className="text-xs text-text-muted mt-0.5">
            {stockName} · 同时研究短期 1–5 个交易日、中期 1–3 个月、长期 1–3 年
          </p>
        </div>
        <button
          onClick={handleDebate}
          disabled={running || hasActiveRecord || isRunning}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isRunning ? (
            <><RefreshCw className="w-4 h-4 animate-spin" /> 分析中...</>
          ) : (
            <><MessageSquare className="w-4 h-4" /> 触发辩论</>
          )}
        </button>
      </div>

      <section aria-label="分析历史" className="mb-4 rounded-md border border-bg-tertiary p-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-sm font-medium">分析历史</h4>
          <button onClick={() => void history.refetch()} className="text-xs text-accent-blue">刷新记录</button>
        </div>
        {history.isPending && <p className="text-xs text-text-muted mt-2">正在读取历史记录…</p>}
        {history.isError && <p className="text-xs text-accent-red mt-2">历史记录加载失败，请刷新记录重试。</p>}
        {!history.isPending && !history.isError && records.length === 0 && (
          <p className="text-xs text-text-muted mt-2">暂无完整分析记录。旧复盘摘要可在“研究与复盘”查看。</p>
        )}
        {records.length > 0 && (
          <ul className="mt-2 max-h-48 overflow-y-auto space-y-2">
            {records.map((record) => (
              <li key={record.session_id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span>{new Date(record.created_at).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai"})}（北京时间） · {
                  record.status === "completed" ? "已完成" : record.status === "failed" ? "失败" : "分析中"
                }</span>
                {record.status === "completed" ? (
                  <button className="text-accent-blue" onClick={() => setSelectedHistory(record.session_id)}>
                    {effectiveSessionId === record.session_id ? "正在查看" : "查看结果"}
                  </button>
                ) : record.status === "failed" ? (
                  <span className="text-accent-red">{record.error || "分析未完成"}</span>
                ) : <span className="text-text-muted">完成后可查看，无需重复提交</span>}
              </li>
            ))}
          </ul>
        )}
        {(records.length >= 50 || historyOffset > 0) && (
          <div className="flex gap-4 mt-3 text-xs text-accent-blue">
            <button disabled={historyOffset === 0} onClick={() => setHistoryOffset(Math.max(0, historyOffset - 50))}>较新记录</button>
            <button disabled={records.length < 50} onClick={() => setHistoryOffset(historyOffset + 50)}>更早记录</button>
          </div>
        )}
      </section>
      {viewingHistory && selectedRecord && (
        <p className="mb-3 text-xs text-text-muted">
          历史分析 · {new Date(selectedRecord.created_at).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai"})}（北京时间）。以下为当时的数据与结论。
        </p>
      )}

      {/* 错误态 */}
      {visibleError && (
        <div className="p-3 rounded-md bg-accent-red/10 border border-accent-red/20 text-sm text-accent-red mb-3">
          {visibleError}
        </div>
      )}

      {/* 加载中 — 骨架屏 */}
      {isRunning && !results && (
        <div className="space-y-2" role="status">
          <p className="text-sm text-text-muted">正在进行多轮分析与交叉审阅，可能需要数分钟，请勿重复提交。</p>
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-3 rounded-md bg-bg-primary/50 border border-bg-tertiary animate-pulse"
            >
              <div className="w-8 h-8 rounded-full bg-bg-tertiary" />
              <div className="flex-1">
                <div className="h-3 w-32 bg-bg-tertiary rounded" />
                <div className="h-2 w-48 bg-bg-tertiary rounded mt-2" />
              </div>
              <div className="h-4 w-16 bg-bg-tertiary rounded" />
            </div>
          ))}
        </div>
      )}

      {/* 结果 — 来自后端真实辩论数据 */}
      {results && (
        <>
          {limitations.length > 0 && (
            <div role="status" className="p-3 mb-3 rounded-md border border-amber-500/30 bg-amber-500/10 text-sm text-text-primary">
              <p className="font-semibold">本次研究的限制</p>
              <ul className="mt-1 space-y-1 list-disc pl-4">
                {limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          )}
          <HorizonResearch analyses={results.analyses} />
          <details className="rounded-md border border-bg-tertiary p-3">
            <summary className="cursor-pointer text-sm">原始流派论证（未限定周期的历史方向不作结论）</summary>
            <AgentAnalysisList analyses={results.analyses} />
          </details>
        </>
      )}

      {/* 空态 */}
      {!triggered && !visibleError && !results && (
        <div className="text-center py-8">
          <div className="text-3xl mb-3">🤖</div>
          <p className="text-sm text-text-muted">
            点击「触发辩论」生成该股各流派分析；成功返回后可逐个展开依据和风险。
          </p>
        </div>
      )}
    </div>
  );
}
