import assert from "node:assert/strict";
import test from "node:test";

import { marketNoticeFacts } from "../lib/market-notice.ts";
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
