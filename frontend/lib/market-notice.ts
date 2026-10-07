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
    const conflicts = new Set(meta.source_diagnostics.filter((item) => item.status === "conflicted").map((item) => item.upstream_id));
    const failed = meta.failed_sources.filter((source) => !conflicts.has(source) || meta.source_diagnostics.some((item) => item.upstream_id === source && item.status === "failed"));
    if (failed.length) facts.push(`失败来源：${failed.join("、")}`);
    if (conflicts.size) facts.push(`冲突来源：${[...conflicts].join("、")}`);
  }
  for (const limitation of visibleLimitations) {
    facts.push(limitation.message);
  }
  return facts;
}

/** Keep stale/failed status prominent; taxonomy notes belong in the disclosure. */
export function boardNoticeSummary(meta: MarketMeta | undefined, refreshError = false): string | null {
  if (!meta?.limitations.some(item => item.code.startsWith("BOARD_"))) return null;
  if (refreshError || meta.status === "stale") {
    return "刷新未成功，当前为历史快照；排名仅对应所示行情时间。";
  }
  if (meta.failed_sources.length) return "部分板块来源刷新失败，当前仅展示可用数据。";
  return "东方财富快照已加载；请结合行情时间查看排名。";
}
