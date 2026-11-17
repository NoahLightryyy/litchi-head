"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseFiveDay, requireFiveDayDisplay } from "@/lib/five-day-display";

/** Same key for the full five-day view and current-session fallback; no duplicate calls. */
export function useFiveDayDisplay(code: string, enabled = true) {
  return useQuery({
    queryKey: ["stocks", code, "five-day-display"],
    queryFn: async ({ signal }) => requireFiveDayDisplay(parseFiveDay(
      await api.getRaw(`/stocks/${code}/intraday-five-day-display`, undefined,
        { signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]) }), code)),
    enabled: !!code && enabled, retry: false, staleTime: 30000,
    refetchInterval: enabled ? 30000 : false,
  });
}
