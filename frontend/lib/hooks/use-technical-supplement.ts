"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseTechnicalSupplement } from "@/lib/technical-supplement";

export function useTechnicalSupplement(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "technical-research"],
    queryFn: async ({ signal }) => parseTechnicalSupplement(await api.getRaw(
      `/stocks/${code}/technical-research`, undefined,
      { signal: AbortSignal.any([signal, AbortSignal.timeout(32_000)]) }), code),
    retry: false, staleTime: 300_000, refetchOnWindowFocus: false,
  });
}
