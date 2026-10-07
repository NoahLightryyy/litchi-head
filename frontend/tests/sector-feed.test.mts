import assert from "node:assert/strict";
import test from "node:test";
import { loadSectorFeed } from "../lib/sector-feed.ts";
import type { MarketEnvelope, SectorItem } from "../lib/types/market.ts";

function value(source: SectorItem["source"]): MarketEnvelope<SectorItem[]> {
  return {data: [{id: source === "sina" ? "sina:new_yyzz" : "BK1216", source,
    name: "医药", category: "industry", fund_flow: source === "sina" ? null : 61.9,
    net_flow: source === "sina" ? 12.3 : null, as_of: null,
    change_pct: 2, rank: 1, heat: "medium", top_stocks: [], snapshot_may_be_delayed: true}],
  meta: {status: "partial", cached: false, latency_ms: 1, missing_codes: [],
    failed_sources: [], limitations: [], source_diagnostics: [],
    sort_requested: null, sort_applied: null}};
}

test("同名板块保留各来源资金字段，不拼接或替代", async () => {
  const [east, sina] = await Promise.all([
    loadSectorFeed("eastmoney", async () => value("eastmoney")),
    loadSectorFeed("sina", async () => value("sina")),
  ]);
  assert.equal(east.data[0].fund_flow, 61.9);
  assert.equal(east.data[0].net_flow, null);
  assert.equal(sina.data[0].fund_flow, null);
  assert.equal(sina.data[0].net_flow, 12.3);
  assert.notEqual(east.data[0].id, sina.data[0].id);
});

test("东财失败不影响新浪，旧快照状态原样保留", async () => {
  const error = {status: 503, code: "MARKET_SECTORS_FAILED"};
  const outcomes = await Promise.allSettled([
    loadSectorFeed("eastmoney", async () => {throw error;}),
    loadSectorFeed("sina", async () => value("sina")),
  ]);
  assert.equal(outcomes[0].status, "rejected");
  assert.equal(outcomes[1].status, "fulfilled");
  const stale = value("eastmoney");
  stale.meta.status = "stale"; stale.meta.cached = true;
  stale.meta.failed_sources = ["industry", "concept"];
  assert.equal(await loadSectorFeed("eastmoney", async () => stale), stale);
});

test("禁止来源错配或混合，空数据及请求异常不伪装成功", async () => {
  await assert.rejects(loadSectorFeed("eastmoney", async () => value("sina")), /来源/);
  const mixed = value("eastmoney"); mixed.data.push(...value("sina").data);
  await assert.rejects(loadSectorFeed("eastmoney", async () => mixed), /来源/);
  const empty = value("sina"); empty.data = []; empty.meta.status = "empty";
  assert.equal(await loadSectorFeed("sina", async () => empty), empty);
  const error = new Error("aborted");
  await assert.rejects(loadSectorFeed("sina", async () => {throw error;}), e => e === error);
});
