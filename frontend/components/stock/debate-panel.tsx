"use client";

import { useState } from "react";
import { MessageSquare, RefreshCw, Info } from "lucide-react";
import { useRunDebate, useDebateResult } from "@/lib/hooks/use-debate";
import type { AgentAnalysis, VoteSummary } from "@/lib/types/debate";

interface DebatePanelProps {
  stockCode: string;
  stockName: string;
}

/** AI 辩论面板：触发辩论 → 后端真实调用 → 展示大师分析 → 共识汇总 */
export function DebatePanel({ stockCode, stockName }: DebatePanelProps) {
  const { trigger, sessionId, running } = useRunDebate();
  const [error, setError] = useState<string | null>(null);
  const [triggered, setTriggered] = useState(false);

  const { data: debateResult, isLoading: polling } = useDebateResult(sessionId);

  const handleDebate = async () => {
    setError(null);
    setTriggered(true);
    try {
      await trigger({ stock_code: stockCode, question: `${stockName} 投资分析` });
    } catch (e) {
      setError("辩论触发失败，请检查后端服务是否运行");
    }
  };

  const isRunning = running || polling;
  const results = debateResult?.vote_summary
    ? {
        voteSummary: debateResult.vote_summary as VoteSummary,
        analyses: (debateResult.analyses ?? []) as AgentAnalysis[],
      }
    : null;

  return (
    <div>
      {/* 头部 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">AI 多大师辩论决策</h3>
          <p className="text-xs text-text-muted mt-0.5">
            {stockName} · 后端 LangGraph 多 Agent 辩论
          </p>
        </div>
        <button
          onClick={handleDebate}
          disabled={isRunning}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isRunning ? (
            <><RefreshCw className="w-4 h-4 animate-spin" /> 分析中...</>
          ) : (
            <><MessageSquare className="w-4 h-4" /> 触发辩论</>
          )}
        </button>
      </div>

      {/* 错误态 */}
      {error && (
        <div className="p-3 rounded-md bg-accent-red/10 border border-accent-red/20 text-sm text-accent-red mb-3">
          {error}
        </div>
      )}

      {/* 加载中 — 骨架屏 */}
      {isRunning && !results && (
        <div className="space-y-2">
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
          {/* 共识卡片 */}
          <div className="p-4 rounded-md bg-accent-green/5 border border-accent-green/20 mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-accent-green">共识结果</span>
              <span className="text-xs text-text-muted">
                {debateResult?.total_latency_ms
                  ? `${(debateResult.total_latency_ms / 1000).toFixed(1)}s`
                  : ""}
              </span>
            </div>
            <div className="flex items-center gap-6">
              <span
                className={`text-2xl font-bold ${
                  results.voteSummary.consensus === "看涨"
                    ? "text-accent-green"
                    : "text-accent-red"
                }`}
              >
                {results.voteSummary.consensus}
              </span>
              <div className="flex gap-4 text-sm">
                <KpiItem
                  label="加权评分"
                  value={results.voteSummary.weighted_score.toFixed(1)}
                />
                <div>
                  <span className="text-text-muted">置信度</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-number text-text-primary">
                      {`${(results.voteSummary.confidence * 100).toFixed(0)}%`}
                    </span>
                    <span className="text-[10px] text-text-muted bg-bg-tertiary px-1 rounded">
                      校准
                    </span>
                  </div>
                </div>
                {results.voteSummary.direction_distribution && (
                  <KpiItem
                    label="看涨"
                    value={`${results.voteSummary.direction_distribution.Bullish ?? 0}`}
                  />
                )}
              </div>
            </div>
            {/* 置信度条 */}
            <div className="mt-3">
              <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${results.voteSummary.confidence * 100}%`,
                    backgroundColor:
                      results.voteSummary.confidence >= 0.7
                        ? "rgb(34, 197, 94)"
                        : results.voteSummary.confidence >= 0.4
                          ? "rgb(234, 179, 8)"
                          : "rgb(239, 68, 68)",
                  }}
                />
              </div>
            </div>
          </div>

          {/* 大师分析列表 */}
          {results.analyses.map((a, i) => (
            <div
              key={a.agent_name ?? i}
              className="flex items-center justify-between p-3 rounded-md bg-bg-primary/50 border border-bg-tertiary mb-2"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center text-sm">
                  {["🦅", "🦊", "🐺", "🦉", "🦄", "🐻", "🐯"][i] ?? "🤖"}
                </div>
                <div>
                  <span className="text-sm font-medium text-text-primary">
                    {a.skill_name || a.agent_name}
                  </span>
                  <span className="text-xs text-text-muted ml-2">
                    {a.agent_name.replace("master.", "")}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {/* 方向 */}
                <span
                  className={`font-number text-sm ${
                    a.direction === "Bullish"
                      ? "text-accent-green"
                      : a.direction === "Bearish"
                        ? "text-accent-red"
                        : "text-accent-gold"
                  }`}
                >
                  {a.direction === "Bullish"
                    ? "看涨"
                    : a.direction === "Bearish"
                      ? "看跌"
                      : "中性"}
                </span>
                {/* 评分 */}
                <span className="font-number text-sm text-text-secondary">
                  {a.score}/100
                </span>
                {/* 置信度条 */}
                <div className="flex items-center gap-1.5 min-w-[80px]">
                  <div className="flex-1 h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${a.confidence * 100}%`,
                        backgroundColor:
                          a.confidence >= 0.7
                            ? "rgb(34, 197, 94)"
                            : a.confidence >= 0.4
                              ? "rgb(234, 179, 8)"
                              : "rgb(239, 68, 68)",
                      }}
                    />
                  </div>
                  <span className="font-number text-xs text-text-muted w-8 text-right">
                    {(a.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          ))}

          {/* 偏斜公示 */}
          {results.voteSummary.bias_report && (
            <div className="mt-3 p-3 rounded-md border border-bg-tertiary bg-bg-primary/30">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Info className="w-3 h-3 text-text-muted" />
                <span className="text-xs text-text-muted">偏斜公示</span>
              </div>
              <div className="flex gap-3 text-xs">
                <span className="text-text-muted">
                  看涨 {results.voteSummary.bias_report.bullish_count}/
                  看跌 {results.voteSummary.bias_report.bearish_count}/
                  中性 {results.voteSummary.bias_report.neutral_count}
                </span>
                <span className="text-text-muted">
                  共识强度: {(results.voteSummary.bias_report.consensus_strength * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          )}
        </>
      )}

      {/* 空态 */}
      {!triggered && !error && (
        <div className="text-center py-8">
          <div className="text-3xl mb-3">🤖</div>
          <p className="text-sm text-text-muted">
            点击「触发辩论」调用后端 LangGraph 开始 AI 多大师分析
          </p>
        </div>
      )}
    </div>
  );
}

function KpiItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-text-muted">{label}</span>{" "}
      <span className="font-number text-text-primary">{value}</span>
    </div>
  );
}
