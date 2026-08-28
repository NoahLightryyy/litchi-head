import type { MarketMeta } from "@/lib/types/market";
import { marketNoticeFacts } from "@/lib/market-notice";

interface MarketDataNoticeProps {
  meta?: MarketMeta;
  refreshError?: boolean;
}

export function MarketDataNotice({ meta, refreshError }: MarketDataNoticeProps) {
  const facts = marketNoticeFacts(meta, refreshError);
  if (facts.length === 0) return null;

  return (
    <div className="mb-3 rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
      {facts.join("；")}
    </div>
  );
}
