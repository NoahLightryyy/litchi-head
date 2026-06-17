"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { runDebate, fetchDebateResult, fetchTrustReport, fetchTrustLeaderboard } from "@/lib/api/debate";
import type { DebateResult, TrustReport, DebateRequest } from "@/lib/types/debate";

/* ── 触发辩论（mutation hook） ── */
export function useRunDebate() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const trigger = useCallback(async (req: DebateRequest) => {
    setRunning(true);
    try {
      const { session_id } = await runDebate(req);
      setSessionId(session_id);
      return session_id;
    } finally {
      setRunning(false);
    }
  }, []);

  return { trigger, sessionId, running };
}

/* ── 辩论结果（轮询） ── */
export function useDebateResult(sessionId: string | null) {
  return useQuery({
    queryKey: ["debate", "result", sessionId],
    queryFn: () => fetchDebateResult(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      // 未完成时每 2 秒轮询
      const data = query.state.data as DebateResult | undefined;
      return data?.vote_summary ? false : 2000;
    },
    staleTime: Infinity,
  });
}

/* ── 信任度报告 ── */
export function useTrustReport(agentName: string) {
  return useQuery({
    queryKey: ["trust", "report", agentName],
    queryFn: () => fetchTrustReport(agentName),
    staleTime: 300_000,           // 5 分钟缓存
    enabled: !!agentName,
  });
}

/* ── 信任度排行榜 ── */
export function useTrustLeaderboard() {
  return useQuery({
    queryKey: ["trust", "leaderboard"],
    queryFn: () => fetchTrustLeaderboard(),
    staleTime: 300_000,
  });
}
