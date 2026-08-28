import type { MarketMeta } from "@/lib/types/market";

export function marketNoticeFacts(
  meta: MarketMeta | undefined,
  refreshError: boolean = false,
): string[] {
  const facts: string[] = [];
  if (refreshError) facts.push("刷新失败，保留上次数据");
  if (meta?.status === "stale") facts.push("当前显示缓存数据");
  if (meta?.missing_codes.length) {
    facts.push(`缺少代码：${meta.missing_codes.join("、")}`);
  }

  const visibleLimitations = (meta?.limitations ?? []).filter(
    (limitation) => limitation.code !== "INDEX_SINGLE_SOURCE",
  );
  const onlySingleSourceLimitations =
    (meta?.limitations.length ?? 0) > 0 && visibleLimitations.length === 0;

  // 单源指数已经在各指数卡片内轻量披露，不重复展示技术来源告警。
  if (meta?.failed_sources.length && !onlySingleSourceLimitations) {
    facts.push(`失败来源：${meta.failed_sources.join("、")}`);
  }
  for (const limitation of visibleLimitations) {
    facts.push(limitation.message);
  }
  return facts;
}
