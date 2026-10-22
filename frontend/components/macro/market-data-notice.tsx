import type { MarketMeta } from "@/lib/types/market";
import { boardNoticeSummary, marketNoticeFacts, marketNoticeLabel } from "@/lib/market-notice";

interface MarketDataNoticeProps {
  meta?: MarketMeta;
  refreshError?: boolean;
}

export function MarketDataNotice({ meta, refreshError }: MarketDataNoticeProps) {
  const facts = marketNoticeFacts(meta, refreshError);
  if (facts.length === 0) return null;
  const summary = boardNoticeSummary(meta, refreshError);

  return (
    <details className="mb-3 text-xs text-text-muted">
      <summary className="w-fit cursor-pointer rounded-sm focus-visible:outline-2 focus-visible:outline-accent-blue">
        {marketNoticeLabel(meta, refreshError)}
      </summary>
      <div className="mt-2 rounded-md border border-bg-tertiary bg-bg-secondary px-3 py-2">
        {summary && <p className="font-medium text-text-primary">{summary}</p>}
        <ul className="mt-1 list-disc space-y-1 pl-4">
          {facts.map((fact, index) => <li key={`${index}:${fact}`}>{fact}</li>)}
        </ul>
      </div>
    </details>
  );
}
