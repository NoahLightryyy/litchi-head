"use client";

import { useState, useCallback, useRef } from "react";
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

/* ── 辩论结果（轮询，最大 60 次 ≈ 120 秒兜底） ── */
export function useDebateResult(sessionId: string | null) {
  const pollCountRef = useRef(0);
  const MAX_POLLS = 60;

  return useQuery({
    queryKey: ["debate", "result", sessionId],
    queryFn: () => fetchDebateResult(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const data = query.state.data as DebateResult | undefined;

      // 辩论完成 → 停
      if (data?.vote_summary) return false;

      // 超过最大轮询次数 → 停
      pollCountRef.current += 1;
      if (pollCountRef.current >= MAX_POLLS) return false;

      return 2000;
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
