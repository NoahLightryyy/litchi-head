/** Successful maps stay fresh; a failed attempt must not permanently disable generation. */
export function retryChainDraft(failures: number, error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const e = error as {code?: string; status?: number};
  if (e.code === 'CHAIN_DRAFT_BUSY') return failures < 6;
  if (e.code === 'NETWORK_ERROR' || e.status === 429) return failures < 2;
  if (e.code === 'CHAIN_DRAFT_TIMEOUT' || e.code === 'CHAIN_DRAFT_FAILED') return failures < 1;
  return false;
}

export const chainDraftRecovery = {
  staleTime: Infinity,
  refetchOnWindowFocus: false,
  refetchOnReconnect: true,
  refetchOnMount: true,
  retry: retryChainDraft,
  retryDelay: (attempt: number) => Math.min(5000 * (attempt + 1), 15000),
} as const;
