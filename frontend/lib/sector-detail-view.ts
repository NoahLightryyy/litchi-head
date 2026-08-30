import type { SectorDetail } from "@/lib/types/market";

export type SectorDetailViewMode = "loading" | "error" | "empty" | "data";

interface SectorDetailViewState {
  sector: SectorDetail | undefined;
  isLoading: boolean;
  isError: boolean;
}

export function resolveSectorDetailViewMode({
  sector,
  isLoading,
  isError,
}: SectorDetailViewState): SectorDetailViewMode {
  if (isLoading) return "loading";
  if (isError) return "error";
  if (!sector) return "empty";
  return "data";
}
