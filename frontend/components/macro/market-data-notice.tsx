import type { MarketMeta } from "@/lib/types/market";
import { boardNoticeSummary, marketNoticeFacts } from "@/lib/market-notice";

interface MarketDataNoticeProps {
  meta?: MarketMeta;
  refreshError?: boolean;
}

export function MarketDataNotice({ meta, refreshError }: MarketDataNoticeProps) {
  const facts = marketNoticeFacts(meta, refreshError);
  if (facts.length === 0) return null;

  const summary = boardNoticeSummary(meta, refreshError);
  if (summary) {
    const snapshot = meta?.limitations.find(item => item.code === "BOARD_SNAPSHOT_MAY_BE_DELAYED");
    const failures = meta?.limitations.filter(item => item.code === "BOARD_REFRESH_FAILED") ?? [];
    return (
      <div className="mb-3 rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
        <p role="status" className="font-medium">{summary}</p>
        {snapshot && <p className="mt-1">{snapshot.message}</p>}
        {failures.length > 0 && <p className="mt-1">{failures.map(item => item.message).join("；")}</p>}
        <details className="mt-2">
          <summary className="cursor-pointer">查看来源诊断与统计口径</summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {facts.map((fact, index) => <li key={`${index}:${fact}`}>{fact}</li>)}
          </ul>
        </details>
      </div>
    );
  }

  return (
    <div className="mb-3 rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
      {facts.join("；")}
    </div>
  );
}
