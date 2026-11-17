"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseRawDaily } from "@/lib/raw-daily";

/** Shared identity/key lets charts and indicator cards reuse the same dated candles. */
export function useRawDaily(code: string, days = 240, enabled = true) {
  return useQuery({ queryKey: ["stocks", code, "raw-daily-display", days],
    queryFn: async ({ signal }) => parseRawDaily(await api.getRaw(`/stocks/${code}/kline-raw-display`, { days: String(days) },
      { signal: AbortSignal.any([signal, AbortSignal.timeout(15_000)]) }), code),
    enabled, retry: false, staleTime: 300_000 });
}
