"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRetroRecords,
  fetchRetroSummary,
  updateRetroAction,
  updateRetroOutcome,
  refreshRetroRecords,
  deleteRetroRecord,
} from "@/lib/api/retro";
import type { RetroRecord } from "@/lib/types/retro";

/* ── 复盘记录列表 ── */
export function useRetroRecords(params?: {
  stock_code?: string;
  outcome?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["retro", "records", params],
    queryFn: () => fetchRetroRecords(params),
    staleTime: 30_000,
  });
}

/* ── 复盘聚合统计 ── */
export function useRetroSummary() {
  return useQuery({
    queryKey: ["retro", "summary"],
    queryFn: () => fetchRetroSummary(),
    staleTime: 30_000,
  });
}

/* ── 更新用户操作 ── */
export function useUpdateAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ recordId, action }: { recordId: string; action: string }) =>
      updateRetroAction(recordId, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retro"] });
    },
  });
}

/* ── 更新实际结果 ── */
export function useUpdateOutcome() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recordId,
      returnPct,
      price,
    }: {
      recordId: string;
      returnPct: number;
      price: number;
    }) => updateRetroOutcome(recordId, returnPct, price),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retro"] });
    },
  });
}

/* ── 批量刷新 ── */
export function useRefreshRetro() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => refreshRetroRecords(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retro"] });
    },
  });
}

/* ── 删除记录 ── */
export function useDeleteRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (recordId: string) => deleteRetroRecord(recordId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retro"] });
    },
  });
}
