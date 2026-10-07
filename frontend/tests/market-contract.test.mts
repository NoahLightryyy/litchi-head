import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  MarketContractError,
  parseHotNewsEnvelope,
  parseIndicesEnvelope,
  parseMacroBriefEnvelope,
  parseSectorDetailEnvelope,
  parseSectorsEnvelope,
  parseSinaMembersEnvelope,
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


test("产业链消费者验证身份、来源和关系引用，兼容旧响应", async () => {
  const { readFileSync } = await import("node:fs");
  const graph = JSON.parse(readFileSync(new URL("../../src/data/catalogs/chain/BK1629.json", import.meta.url), "utf8"));
  const data = { id: "BK1629", name: "AI应用", change_pct: 0, fund_flow: 0,
    heat: "low", chain_map: [], chain_evidence: graph, stocks: [], ai_analysis: "" };
  assert.deepEqual(parseSectorDetailEnvelope({ data, meta: baseMeta }).data.chain_evidence, graph);
  for (const mutate of [
    (g: typeof graph) => { g.sector_code = "BK1650"; },
    (g: typeof graph) => { g.sources[0].url = "javascript:alert(1)"; },
    (g: typeof graph) => { g.nodes[0].source_ids = ["unknown"]; },
    (g: typeof graph) => { g.sources[0].published_on = "2024-02-31"; },
    (g: typeof graph) => { g.edges = [{ source_node: "base", target_node: "model", relation: "supplies", source_ids: [g.sources[0].id], description: "invalid" }]; },
  ]) {
    const invalid = structuredClone(graph); mutate(invalid);
    assert.throws(() => parseSectorDetailEnvelope({ data: { ...data, chain_evidence: invalid }, meta: baseMeta }), MarketContractError);
  }
  assert.equal(parseSectorDetailEnvelope({ data: { ...data, chain_evidence: null }, meta: baseMeta }).data.chain_evidence, null);
});


test("板块报价缺失时保留成分股，要求partial与明确诊断", () => {
  const envelope = {
    data: { id: "BK0596", name: "融资融券", change_pct: null, fund_flow: null,
      heat: "medium", chain_map: [], ai_analysis: "", stocks: [
        {code: "000001", name: "平安银行", price: 10, change_pct: 1, fund_flow: 2, ai_rating: "B"},
      ] },
    meta: { ...baseMeta, status: "partial", limitations: [
      {code: "BOARD_QUOTE_UNAVAILABLE", message: "板块行情暂不可用", index_code: null},
      {code: "FUND_FLOW_UNAVAILABLE", message: "暂无数据", index_code: null},
    ] },
  };
  const parsed = parseSectorDetailEnvelope(envelope);
  assert.equal(parsed.data.change_pct, null);
  assert.equal(parsed.data.stocks.length, 1);
  assert.throws(() => parseSectorDetailEnvelope({ ...envelope,
    meta: {...envelope.meta, status: "success"} }), MarketContractError);
  assert.throws(() => parseSectorDetailEnvelope({ ...envelope,
    meta: {...envelope.meta, limitations: envelope.meta.limitations.slice(1)} }), MarketContractError);
  assert.throws(() => parseSectorDetailEnvelope({ ...envelope,
    data: {...envelope.data, change_pct: "暂无数据"} }), MarketContractError);
});


test("断源历史榜单保留时间、排序和用户可见限制", async () => {
  const { marketNoticeFacts } = await import("../lib/market-notice.ts");
  const value = {
    data: [{ id: "BK0001", name: "历史板块", change_pct: 1.2, fund_flow: 1,
      heat: "medium", top_stocks: [], rank: 1, category: "industry",
      as_of: "2026-09-28T07:00:00Z", source: "eastmoney", snapshot_may_be_delayed: true }],
    meta: { ...baseMeta, status: "stale", cached: true, failed_sources: ["industry", "concept"],
      sort_requested: "fund_flow", sort_applied: "fund_flow",
      limitations: [{ code: "BOARD_HISTORY_ONLY", message: "历史排名不代表当前行情", index_code: null }] },
  };
  const parsed = parseSectorsEnvelope(value);
  assert.equal(parsed.data[0].as_of, "2026-09-28T07:00:00Z");
  assert.equal(parsed.meta.status, "stale");
  assert.ok(marketNoticeFacts(parsed.meta).includes("历史排名不代表当前行情"));
});


test("新浪补充字段必须区分主力、净流入和服务时间", () => {
  const data = [{ id: "sina:new_test", name: "测试", change_pct: 1.2, fund_flow: null,
    net_flow: 2, service_updated_at: "2026-09-30T15:01:48+08:00", source: "sina",
    as_of: null, category: "industry", snapshot_may_be_delayed: true,
    heat: "medium", top_stocks: [], rank: 1 }];
  const meta = { ...baseMeta, status: "partial", sort_applied: "net_flow", limitations:
    ["SINA_BOARD_BASIS", "FUND_FLOW_UNAVAILABLE", "SOURCE_SERVICE_TIME_ONLY"].map(code => ({ code, message: code, index_code: null })) };
  assert.equal(parseSectorsEnvelope({data, meta}).data[0].net_flow, 2);
  for (const changes of [{ fund_flow: 2 }, { as_of: data[0].service_updated_at },
    { net_flow: NaN }, { service_updated_at: null }, { id: "BK0001" }]) {
    assert.throws(() => parseSectorsEnvelope({data: [{...data[0], ...changes}], meta}), MarketContractError);
  }
  assert.throws(() => parseSectorsEnvelope({data, meta: {...meta, status: "success"}}), MarketContractError);
});


test("新浪成分股核对板块和页码，拒绝缺页、伪实时及非法行情", () => {
  const value = { data: {source: "sina", board_code: "new_swzz", page: 2, page_size: 20, total: 21,
    stocks: [{code: "300199", name: "翰宇药业", price: 23.92, change_pct: 4.9, net_flow: 3.24}],
    service_updated_at: "2026-09-30T15:01:48+08:00", cached: false},
    meta: {...baseMeta, status: "partial", limitations: [{code: "SINA_MEMBER_BASIS", message: "新浪口径", index_code: null}]}};
  assert.equal(parseSinaMembersEnvelope(value, "new_swzz", 2).data.total, 21);
  assert.throws(() => parseSinaMembersEnvelope(value, "gn_other", 2), MarketContractError);
  assert.throws(() => parseSinaMembersEnvelope(value, "new_swzz", 1), MarketContractError);
  for (const stocks of [[], [{...value.data.stocks[0], net_flow: NaN}], [{...value.data.stocks[0], code: "bad"}]]) {
    assert.throws(() => parseSinaMembersEnvelope({...value, data: {...value.data, stocks}}, "new_swzz", 2), MarketContractError);
  }
  assert.throws(() => parseSinaMembersEnvelope({...value, meta: {...value.meta, status: "success"}}, "new_swzz", 2), MarketContractError);
});

test("AH market structure passes the actual sector envelope parser without weakening edge guards", () => {
  const graph = JSON.parse(readFileSync(new URL("../../src/data/catalogs/chain/BK0499.json", import.meta.url), "utf8"));
  const data = { id: "BK0499", name: "AH股", change_pct: null, fund_flow: null,
    heat: "low", chain_map: [], chain_evidence: graph, stocks: [], ai_analysis: "" };
  const meta = { ...baseMeta, status: "partial", limitations: [
    {code: "BOARD_QUOTE_UNAVAILABLE", message: "板块行情暂不可用", index_code: null},
    {code: "FUND_FLOW_UNAVAILABLE", message: "暂无资金数据", index_code: null},
  ] };
  assert.equal(parseSectorDetailEnvelope({ data, meta }).data.chain_evidence?.map_kind, "market_structure");
  for (const fault of ["kind", "edge", "map"]){
    const invalid = structuredClone(graph);
    if (fault === "kind") invalid.nodes[0].kind = "company";
    if (fault === "edge") invalid.edges[0].relation = "supplies";
    if (fault === "map") invalid.map_kind = "industry_chain";
    assert.throws(() => parseSectorDetailEnvelope({ data: { ...data, chain_evidence: invalid }, meta }), MarketContractError);
  }
});
