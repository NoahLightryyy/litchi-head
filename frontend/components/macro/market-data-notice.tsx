import type { MarketMeta, SectorItem } from "@/lib/types/market";
import { boardNoticeSummary, marketNoticeFacts, sectorNoticeFacts } from "@/lib/market-notice";
import { sectorTimeRange } from "@/lib/sector-availability";

interface MarketDataNoticeProps {
  meta?: MarketMeta;
  refreshError?: boolean;
  diagnosticsOnly?: boolean;
  sectors?: SectorItem[];
  paused?: boolean;
}

export function MarketDataNotice({ meta, refreshError, diagnosticsOnly, sectors, paused }: MarketDataNoticeProps) {
  if (sectors?.length) {
    const source = sectors[0].source;
    const { details, warnings } = sectorNoticeFacts(meta);
    const historical = !!refreshError || meta?.status === "stale" ||
      meta?.limitations.some(item => item.code === "BOARD_HISTORY_ONLY");
    const warning = historical || paused || warnings.length > 0 || !!meta?.failed_sources.length;
    const status = paused ? "网络已断开，显示上次行情。"
      : historical ? "更新暂不可用，显示上次行情。"
      : meta?.failed_sources.length ? "部分分类暂不可用，已显示可用数据。"
      : source === "sina" ? "已获取新浪榜单。" : "快照已加载，行情可能延迟。";
    return <div className={`mb-3 rounded-md border px-3 py-2 text-xs ${warning
      ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
      : "border-bg-tertiary bg-bg-secondary text-text-muted"}`}>
      <p role="status">{status} {source === "sina" ? "服务更新时间" : "行情时间"}：{sectorTimeRange(sectors, source)}</p>
      {source === "sina" && <p className="mt-1">来源未提供逐板块报价时间；以上为服务更新时间。</p>}
      {warnings.map(fact => <p key={fact} className="mt-1">{fact}</p>)}
      {details.length > 0 && <details className="mt-2 text-text-muted">
        <summary className="cursor-pointer">来源详情与统计口径</summary>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          {details.map(fact => <li key={fact}>{fact}</li>)}
        </ul>
      </details>}
    </div>;
  }
  const facts = marketNoticeFacts(meta, refreshError);
  if (facts.length === 0) return null;

  if (diagnosticsOnly) {
    return (
      <details className="mb-3 text-xs text-text-muted">
        <summary className="cursor-pointer">查看来源诊断</summary>
        <p className="mt-2">{facts.join("；")}</p>
      </details>
    );
  }

  const summary = boardNoticeSummary(meta, refreshError);
  if (summary) {
    const snapshot = meta?.limitations.find(item => item.code === "BOARD_SNAPSHOT_MAY_BE_DELAYED");
    const { details, warnings } = sectorNoticeFacts(meta);
    const warning = refreshError || meta?.status === "stale" || !!meta?.failed_sources.length || warnings.length > 0;
    return (
      <div className={`mb-3 rounded-md border px-3 py-2 text-xs ${warning ? "border-amber-500/20 bg-amber-500/10 text-amber-700" : "border-bg-tertiary bg-bg-secondary text-text-muted"}`}>
        <p role="status" className="font-medium">{summary}</p>
        {snapshot && <p className="mt-1">{snapshot.message}</p>}
        {warnings.map(fact => <p key={fact} className="mt-1">{fact}</p>)}
        {details.length > 0 && <details className="mt-2 text-text-muted">
          <summary className="cursor-pointer">来源详情与统计口径</summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {details.map(fact => <li key={fact}>{fact}</li>)}
          </ul>
        </details>}
      </div>
    );
  }

  return (
    <div className="mb-3 rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
      {facts.join("；")}
    </div>
  );
}
