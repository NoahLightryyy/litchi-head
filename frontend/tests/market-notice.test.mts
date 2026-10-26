import assert from "node:assert/strict";
import test from "node:test";

import { canCollapseIndexDiagnostics, marketNoticeFacts } from "../lib/market-notice.ts";
import type { MarketMeta } from "../lib/types/market.ts";

const baseMeta: MarketMeta = {
  status: "partial",
  cached: false,
  latency_ms: 10,
  missing_codes: [],
  failed_sources: ["eastmoney"],
  limitations: [],
  source_diagnostics: [],
  sort_requested: null,
  sort_applied: null,
};

test("冲突来源不冒充请求失败，混合失败保留两类事实", () => {
  const diagnostics: MarketMeta["source_diagnostics"] = ["sina", "eastmoney"].map((upstream_id) => ({
    index_code: "000001", source_id: upstream_id, upstream_id, status: "conflicted",
    latency_ms: 1, as_of: null, error_code: "index_quote_conflict", error_message: "来源数据冲突",
  }));
  const meta = { ...baseMeta, failed_sources: ["sina", "eastmoney"], source_diagnostics: diagnostics };
  assert.deepEqual(marketNoticeFacts(meta), ["冲突来源：sina、eastmoney"]);
  diagnostics.push({ ...diagnostics[0], index_code: "399001", status: "failed" });
  assert.deepEqual(marketNoticeFacts(meta), ["失败来源：sina", "冲突来源：sina、eastmoney"]);
});

test("单源指数详情由卡片披露，不重复生成技术告警横条", () => {
  const facts = marketNoticeFacts({
    ...baseMeta,
    limitations: [
      { code: "INDEX_SINGLE_SOURCE", message: "上证指数当前仅一个来源可用", index_code: "000001" },
      { code: "INDEX_SINGLE_SOURCE", message: "深证成指当前仅一个来源可用", index_code: "399001" },
    ],
  });
  assert.deepEqual(facts, []);
});

test("真正影响使用的缺失、陈旧和刷新失败仍然可见", () => {
  const facts = marketNoticeFacts({
    ...baseMeta,
    status: "stale",
    cached: true,
    missing_codes: ["399006"],
    limitations: [
      { code: "INDEX_SINGLE_SOURCE", message: "上证指数当前仅一个来源可用", index_code: "000001" },
      { code: "OTHER_LIMIT", message: "存在其他限制", index_code: null },
    ],
  }, true);
  assert.deepEqual(facts, [
    "刷新失败，保留上次数据",
    "当前显示缓存数据",
    "缺少代码：399006",
    "失败来源：eastmoney",
    "存在其他限制",
  ]);
});

test("板块详情折叠仍明确历史状态，不能冒充休市成功", async () => {
  const { boardNoticeSummary } = await import("../lib/market-notice.ts");
  const meta: MarketMeta = { ...baseMeta, status: "stale", limitations: [
    { code: "BOARD_HISTORY_ONLY", message: "历史快照", index_code: null },
    { code: "BOARD_REFRESH_FAILED", message: "行业刷新失败：上游返回 HTTP 502", index_code: null },
  ] };
  assert.match(boardNoticeSummary(meta)!, /更新暂不可用.*上次行情/);
  assert.ok(marketNoticeFacts(meta).includes("行业刷新失败：上游返回 HTTP 502"));
  assert.match(boardNoticeSummary({ ...meta, status: "partial", failed_sources: [] })!, /快照已加载/);
  assert.match(boardNoticeSummary({ ...meta, status: "partial", failed_sources: [] }, true)!, /更新暂不可用/);
  assert.equal(boardNoticeSummary(baseMeta), null);
});

test("三项指数可用时折叠备用源故障，缺失缓存冲突刷新失败仍突出显示", () => {
  assert.equal(canCollapseIndexDiagnostics(baseMeta, 3), true);
  assert.equal(canCollapseIndexDiagnostics({ ...baseMeta, limitations: [{code: "INDEX_SINGLE_SOURCE", message: "单源", index_code: "000001"}] }, 3), true);
  assert.equal(canCollapseIndexDiagnostics(baseMeta, 2), false);
  assert.equal(canCollapseIndexDiagnostics(baseMeta, 3, true), false);
  assert.equal(canCollapseIndexDiagnostics({ ...baseMeta, status: "stale" }, 3), false);
  assert.equal(canCollapseIndexDiagnostics({ ...baseMeta, cached: true }, 3), false);
  assert.equal(canCollapseIndexDiagnostics({ ...baseMeta, missing_codes: ["399001"] }, 3), false);
  assert.equal(canCollapseIndexDiagnostics({ ...baseMeta, limitations: [{code: "INDEX_PRICE_CONFLICT", message: "冲突", index_code: "000001"}] }, 3), false);
  assert.deepEqual(marketNoticeFacts(baseMeta), ["失败来源：eastmoney"]);
});
