import assert from "node:assert/strict";
import test from "node:test";
import { loadSectorFeed } from "../lib/sector-feed.ts";
import type { MarketEnvelope, SectorItem } from "../lib/types/market.ts";

const value: MarketEnvelope<SectorItem[]> = {data: [], meta: {status: "empty", cached: false,
  latency_ms: 1, missing_codes: [], failed_sources: [], limitations: [], source_diagnostics: [],
  sort_requested: null, sort_applied: null}};

test("只在明确上游503时切备用，并保留原失败来源", async () => {
  let calls = 0;
  const alternative = async () => {calls++; return value;};
  const result = await loadSectorFeed(async () => {throw {code: "MARKET_SECTORS_FAILED", status: 503};}, alternative);
  assert.equal(calls, 1);
  assert.deepEqual(result.meta.failed_sources, ["eastmoney"]);
  assert.deepEqual(await loadSectorFeed(async () => value, alternative), value);
  assert.equal(calls, 1);
});

test("取消、契约错误、失联、其他503不触发源切换", async () => {
  const errors = [new Error("contract"), {code: "NETWORK_ERROR", status: 0},
    {code: "OTHER", status: 503}];
  for (const error of errors) {
    await assert.rejects(loadSectorFeed(async () => {throw error;}, async () => {throw new Error("must not call");}), e => e === error);
  }
  const error = {code: "MARKET_SECTORS_FAILED", status: 503};
  await assert.rejects(loadSectorFeed(async () => {throw error;}, async () => {throw new Error("must not call");}, AbortSignal.abort()), e => e === error);
});
