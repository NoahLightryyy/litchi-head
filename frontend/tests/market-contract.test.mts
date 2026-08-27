import assert from "node:assert/strict";
import test from "node:test";

import {
  MarketContractError,
  parseHotNewsEnvelope,
  parseIndicesEnvelope,
  parseMacroBriefEnvelope,
  parseSectorsEnvelope,
} from "../lib/market-contract.ts";

const baseMeta = {
  status: "success",
  cached: false,
  latency_ms: 12,
  missing_codes: [],
  failed_sources: [],
  limitations: [],
} as const;

test("消费者接受后端冻结的 success 与 partial 指数信封", () => {
  const success = {
    data: [
      { code: "000001", name: "上证指数", price: 3912.52, change: 23.08, change_pct: 0.59 },
    ],
    meta: baseMeta,
  };
  assert.deepEqual(parseIndicesEnvelope(success), success);

  const partial = {
    data: success.data,
    meta: {
      ...baseMeta,
      status: "partial",
      missing_codes: ["399001", "399006"],
    },
  };
  assert.deepEqual(parseIndicesEnvelope(partial), partial);
});

test("消费者拒绝 0.00 指数和状态数据矛盾", () => {
  assert.throws(
    () => parseIndicesEnvelope({
      data: [{ code: "000001", name: "上证指数", price: 0, change: 0, change_pct: 0 }],
      meta: baseMeta,
    }),
    MarketContractError,
  );
  assert.throws(
    () => parseIndicesEnvelope({ data: [], meta: baseMeta }),
    MarketContractError,
  );
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
    }],
    meta: { ...baseMeta, status: "partial", failed_sources: ["concept"] },
  };
  assert.deepEqual(parseSectorsEnvelope(value), value);
  assert.throws(
    () => parseSectorsEnvelope({ ...value, meta: { ...value.meta, failed_sources: [] } }),
    MarketContractError,
  );
});

test("新闻允许缺发布时间但拒绝空标题，并校验 stale 缓存", () => {
  const partial = {
    data: [{ title: "真实快讯", date: null, source: "财新数据通", url: "https://example.com/news" }],
    meta: {
      ...baseMeta,
      status: "partial",
      limitations: [{ code: "PUBLISHED_AT_MISSING", message: "上游未提供发布时间" }],
    },
  };
  assert.deepEqual(parseHotNewsEnvelope(partial), partial);
  assert.throws(
    () => parseHotNewsEnvelope({
      ...partial,
      data: [{ ...partial.data[0], title: "" }],
    }),
    MarketContractError,
  );
  assert.throws(
    () => parseHotNewsEnvelope({
      ...partial,
      meta: { ...partial.meta, status: "stale", cached: false },
    }),
    MarketContractError,
  );
});
