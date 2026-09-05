import assert from "node:assert/strict";
import test from "node:test";

import {
  MarketContractError,
  parseHotNewsEnvelope,
  parseIndicesEnvelope,
  parseMacroBriefEnvelope,
  parseSectorDetailEnvelope,
  parseSectorsEnvelope,
} from "../lib/market-contract.ts";

const baseMeta = {
  status: "success",
  cached: false,
  latency_ms: 12,
  missing_codes: [],
  failed_sources: [],
  limitations: [],
  source_diagnostics: [],
  sort_requested: null,
  sort_applied: null,
} as const;

const verifiedIndex = {
  code: "000001",
  name: "上证指数",
  price: 3912.52,
  change: 23.08,
  change_pct: 0.59,
  as_of: "2026-08-28T10:15:30+08:00",
  source_count: 2,
  display_source: null,
  cached: false,
} as const;

test("价时冲突的有效单源报价继续展示并保留来源；拒绝缺失或错误的来源字段", () => {
  const data = ["000001", "399001", "399006"].map((code) => ({
    ...verifiedIndex, code, source_count: 1, display_source: code === "399001" ? "eastmoney" : "sina",
  }));
  const meta = { ...baseMeta, status: "partial", limitations: data.map((item) => ({
    code: "INDEX_TIMESTAMP_CONFLICT", index_code: item.code, message: "来源数据冲突",
  })) };
  assert.deepEqual(parseIndicesEnvelope({ data, meta }), { data, meta });
  for (const display_source of [undefined, null, 3, ""]) {
    assert.throws(() => parseIndicesEnvelope({ data: [{ ...data[0], display_source }], meta }), MarketContractError);
  }
});

test("消费者接受后端冻结的 success 与 partial 指数信封", () => {
  const success = { data: [verifiedIndex], meta: baseMeta };
  assert.deepEqual(parseIndicesEnvelope(success), success);

  const partial = {
    data: [{ ...verifiedIndex, source_count: 1, display_source: "sina" }],
    meta: { ...baseMeta, status: "partial", missing_codes: ["399001", "399006"] },
  };
  assert.deepEqual(parseIndicesEnvelope(partial), partial);
});

test("消费者拒绝 0.00 指数和状态数据矛盾", () => {
  assert.throws(
    () => parseIndicesEnvelope({ data: [{ ...verifiedIndex, price: 0 }], meta: baseMeta }),
    MarketContractError,
  );
  assert.throws(() => parseIndicesEnvelope({ data: [], meta: baseMeta }), MarketContractError);
});

test("指数校验时间、来源数量及 success/stale 语义", () => {
  assert.throws(
    () => parseIndicesEnvelope({ data: [{ ...verifiedIndex, source_count: 1, display_source: "sina" }], meta: baseMeta }),
    MarketContractError,
  );
  assert.throws(
    () => parseIndicesEnvelope({
      data: [{ ...verifiedIndex, as_of: "2026-08-28T10:15:30" }], meta: baseMeta,
    }),
    MarketContractError,
  );
  const stale = {
    data: [{ ...verifiedIndex, cached: true }],
    meta: { ...baseMeta, status: "stale", cached: true },
  };
  assert.deepEqual(parseIndicesEnvelope(stale), stale);
});

test("empty 信封必须没有可消费数据", () => {
  const indices = { data: [], meta: { ...baseMeta, status: "empty" } };
  assert.deepEqual(parseIndicesEnvelope(indices), indices);

  const brief = { data: null, meta: { ...baseMeta, status: "empty" } };
  assert.deepEqual(parseMacroBriefEnvelope(brief), brief);
  assert.throws(
    () => parseMacroBriefEnvelope({
      data: { summary: "暂无数据", generated_at: "", market_style: "", risk_tips: [], hot_topics: [] },
      meta: { ...baseMeta, status: "empty" },
    }),
    MarketContractError,
  );
});

test("板块 partial 必须披露失败来源", () => {
  const value = {
    data: [{
      id: "BK0001", name: "证券", change_pct: 3.01, fund_flow: 74.22,
      heat: "medium", top_stocks: [], rank: 1,
      category: "industry", as_of: "2026-09-04T15:39:32+08:00", source: "eastmoney", snapshot_may_be_delayed: true,
    }],
    meta: {
      ...baseMeta, status: "partial", failed_sources: ["concept"],
      sort_requested: "fund_flow", sort_applied: "fund_flow",
    },
  };
  assert.deepEqual(parseSectorsEnvelope(value), value);
  assert.throws(
    () => parseSectorsEnvelope({ ...value, meta: { ...value.meta, failed_sources: [] } }),
    MarketContractError,
  );
});

test("资金流未知必须保持 null 并披露实际排序口径", () => {
  const value = {
    data: [{
      id: "BK0001", name: "证券", change_pct: 3.01, fund_flow: null,
      heat: "medium", top_stocks: [], rank: 1,
      category: "industry", as_of: "2026-09-04T15:39:32+08:00", source: "eastmoney", snapshot_may_be_delayed: true,
    }],
    meta: {
      ...baseMeta,
      status: "partial",
      limitations: [{
        code: "FUND_FLOW_UNAVAILABLE", message: "当前来源未提供资金流", index_code: null,
      }],
      sort_requested: "fund_flow",
      sort_applied: "upstream_order",
    },
  };
  assert.deepEqual(parseSectorsEnvelope(value), value);
  assert.throws(
    () => parseSectorsEnvelope({ ...value, meta: { ...value.meta, sort_applied: "fund_flow" } }),
    MarketContractError,
  );
});

test("板块详情接受 nullable 资金流且要求限制说明", () => {
  const detail = {
    id: "BK0001", name: "证券", change_pct: 1.2, fund_flow: null, heat: "medium",
    chain_map: [], ai_analysis: "",
    stocks: [{
      code: "600000", name: "浦发银行", price: 10.2, change_pct: 0.3,
      fund_flow: null, ai_rating: "B",
    }],
  };
  const envelope = {
    data: detail,
    meta: {
      ...baseMeta,
      status: "partial",
      limitations: [{
        code: "FUND_FLOW_UNAVAILABLE", message: "未知值返回 null", index_code: null,
      }],
    },
  };
  assert.deepEqual(parseSectorDetailEnvelope(envelope), envelope);
  assert.throws(
    () => parseSectorDetailEnvelope({ ...envelope, meta: { ...envelope.meta, limitations: [] } }),
    MarketContractError,
  );
});

test("新闻允许缺发布时间但拒绝空标题，并校验 stale 缓存", () => {
  const partial = {
    data: [{ title: "真实快讯", date: null, source: "财新数据通", url: "https://example.com/news" }],
    meta: {
      ...baseMeta,
      status: "partial",
      limitations: [{
        code: "PUBLISHED_AT_MISSING", message: "上游未提供发布时间", index_code: null,
      }],
    },
  };
  assert.deepEqual(parseHotNewsEnvelope(partial), partial);
  assert.throws(
    () => parseHotNewsEnvelope({ ...partial, data: [{ ...partial.data[0], title: "" }] }),
    MarketContractError,
  );
  assert.throws(
    () => parseHotNewsEnvelope({ ...partial, meta: { ...partial.meta, status: "stale", cached: false } }),
    MarketContractError,
  );
});


test("快照 partial 保留榜单，并严格校验来源、分类及带时区时间", () => {
  const item = {
    id: "BK0001", name: "证券", change_pct: 3.01, fund_flow: 74.22,
    heat: "medium", top_stocks: [], rank: 1,
    category: "industry", as_of: "2026-09-04T15:39:32+08:00",
    source: "eastmoney", snapshot_may_be_delayed: true,
  };
  const value = {
    data: [item],
    meta: { ...baseMeta, status: "partial", sort_requested: "fund_flow", sort_applied: "fund_flow",
      limitations: [{ code: "BOARD_SNAPSHOT_MAY_BE_DELAYED", message: "东方财富快照，可能延迟", index_code: null }] },
  };
  assert.deepEqual(parseSectorsEnvelope(value), value);
  assert.equal(parseSectorsEnvelope(value).data[0].fund_flow, 74.22);
  for (const change of [
    { category: "unknown" }, { category: undefined }, { source: "unknown" },
    { as_of: "2026-09-04T15:39:32" }, { snapshot_may_be_delayed: "true" },
  ]) {
    assert.throws(() => parseSectorsEnvelope({ ...value, data: [{ ...item, ...change }] }), MarketContractError);
  }
  assert.equal(parseSectorsEnvelope({ ...value, data: [{ ...item, category: "concept", as_of: null }] }).data[0].category, "concept");
});
