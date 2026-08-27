import type { MarketMeta } from "@/lib/types/market";

interface MarketDataNoticeProps {
  meta?: MarketMeta;
  refreshError?: boolean;
}

export function MarketDataNotice({ meta, refreshError }: MarketDataNoticeProps) {
  const facts: string[] = [];
  if (refreshError) facts.push("刷新失败，保留上次数据");
  if (meta?.status === "stale") facts.push("当前显示缓存数据");
  if (meta?.missing_codes.length) {
    facts.push(`缺少代码：${meta.missing_codes.join("、")}`);
  }
  if (meta?.failed_sources.length) {
    facts.push(`失败来源：${meta.failed_sources.join("、")}`);
  }
  for (const limitation of meta?.limitations ?? []) {
    facts.push(limitation.message);
  }
  if (facts.length === 0) return null;

  return (
    <div className="mb-3 rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
      {facts.join("；")}
    </div>
  );
}
