import type { MarketMeta } from "@/lib/types/market";
import { SECTOR_SCOPE_NOTES } from "./sector-availability.ts";

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
    return "更新暂不可用，显示上次行情。";
  }
  if (meta.failed_sources.length) return "部分板块来源刷新失败，当前仅展示可用数据。";
  return "快照已加载，行情可能延迟。";
}

/** Separate actionable failures from informational scope notes; never hide unknown limits. */
export function sectorNoticeFacts(meta: MarketMeta | undefined): { details: string[]; warnings: string[] } {
  const details = new Set<string>();
  const warnings = new Set<string>();
  const sina = meta?.limitations.some(item => item.code === "SINA_BOARD_BASIS");
  const failures = meta?.limitations.filter(item => item.code === "BOARD_REFRESH_FAILED") ?? [];
  // One status line already explains cached/history/delayed data and its timestamp.
  const summarized = new Set(["BOARD_HISTORY_ONLY", "BOARD_SNAPSHOT_MAY_BE_DELAYED", "SOURCE_SERVICE_TIME_ONLY"]);
  for (const item of meta?.limitations ?? []) {
    if (summarized.has(item.code)) continue;
    if (item.code === "BOARD_REFRESH_FAILED" || SECTOR_SCOPE_NOTES.has(item.code) ||
      (sina && item.code === "FUND_FLOW_UNAVAILABLE")) details.add(item.message);
    else warnings.add(item.message);
  }
  if (meta?.failed_sources.length && !failures.length) details.add(`未更新分类或来源：${meta.failed_sources.join("、")}`);
  if (meta?.missing_codes.length) warnings.add(`缺少代码：${meta.missing_codes.join("、")}`);
  return { details: [...details], warnings: [...warnings] };
}

/** Only redundant-source diagnostics may be collapsed; data quality stays visible. */
export function canCollapseIndexDiagnostics(meta: MarketMeta | undefined, count: number, refreshError = false): boolean {
  return !!meta && count === 3 && !refreshError && !meta.cached &&
    (meta.status === "success" || meta.status === "partial") &&
    meta.missing_codes.length === 0 &&
    meta.limitations.every(item => item.code === "INDEX_SINGLE_SOURCE") &&
    !meta.source_diagnostics.some(item => item.status === "conflicted");
}
