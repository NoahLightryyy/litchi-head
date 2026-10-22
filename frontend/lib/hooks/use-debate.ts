"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { runDebate, fetchDebateHistory, fetchDebateResult, fetchTrustReport, fetchTrustLeaderboard } from "@/lib/api/debate";
import type { DebateResult, DebateRequest } from "@/lib/types/debate";
import {
  INITIAL_DEBATE_REQUEST_STATE,
  advanceDebatePoll,
  debateRequestReducer,
} from "@/lib/debate-session";

/* ── 触发辩论（mutation hook） ── */
export function useRunDebate() {
  const [{ sessionId, running }, dispatch] = useReducer(
    debateRequestReducer,
    INITIAL_DEBATE_REQUEST_STATE,
  );

  const trigger = useCallback(async (req: DebateRequest) => {
    // SAFE-1：新请求一开始就解除旧 session，不能等成功后才替换。
    dispatch({ type: "start" });
    try {
      const { session_id } = await runDebate(req);
      dispatch({ type: "succeeded", sessionId: session_id });
      return session_id;
    } catch (error) {
      dispatch({ type: "failed" });
      throw error;
    }
  }, []);

  return { trigger, sessionId, running };
}

/* 服务端确认运行时持续读取结果；无运行状态时保留60次轮询兜底。 */
export function useDebateResult(sessionId: string | null, serverRunning = false) {
  const pollTrackerRef = useRef({ sessionId, count: 0 });
  const [timedOutSessionId, setTimedOutSessionId] = useState<string | null>(null);
  const MAX_POLLS = 60;

  useEffect(() => {
    pollTrackerRef.current = { sessionId, count: 0 };
  }, [sessionId]);

  const query = useQuery({
    queryKey: ["debate", "result", sessionId],
    queryFn: () => fetchDebateResult(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const data = query.state.data as DebateResult | undefined;
      const decision = advanceDebatePoll(
        pollTrackerRef.current.count,
        Boolean(data?.vote_summary),
        serverRunning ? Infinity : MAX_POLLS,
      );
      pollTrackerRef.current.count = decision.nextCount;

      if (decision.timedOut && sessionId) {
        setTimedOutSessionId(sessionId);
      }

      return decision.continuePolling ? 2000 : false;
    },
    staleTime: Infinity,
  });

  return {
    ...query,
    isTimedOut: Boolean(!serverRunning && sessionId && timedOutSessionId === sessionId),
  };
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

export function useDebateHistory(stockCode: string, offset = 0) {
  return useQuery({
    queryKey: ["debate", "history", stockCode, offset],
    queryFn: () => fetchDebateHistory(stockCode, offset),
    refetchInterval: 10_000,
    staleTime: 0,
  });
}
