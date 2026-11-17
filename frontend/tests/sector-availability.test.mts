import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as availability from "../lib/sector-availability.ts";
import * as notices from "../lib/market-notice.ts";
import type { MarketMeta, SectorItem } from "../lib/types/market.ts";

const meta = (extra: Partial<MarketMeta> = {}): MarketMeta => ({
  status: "partial", cached: false, latency_ms: 1, missing_codes: [], failed_sources: [],
  limitations: [], source_diagnostics: [], sort_requested: null, sort_applied: null, ...extra,
});
const note = (code: string, message = code) => ({ code, message, index_code: null });
const item = (source: SectorItem["source"]): SectorItem => ({
  source, id: source === "sina" ? "sina:test" : "BK0001", name: "测试板块", rank: 1,
  category: "industry", as_of: source === "sina" ? null : "2026-10-26T15:39:30+08:00",
  service_updated_at: source === "sina" ? "2026-10-26T15:01:54+08:00" : null,
  change_pct: 1, fund_flow: source === "sina" ? null : 1, net_flow: source === "sina" ? 2 : null,
  heat: "low", top_stocks: [], snapshot_may_be_delayed: true,
});
const east = (extra: Partial<MarketMeta> = {}) => ({
  data: { data: [item("eastmoney")], meta: meta(extra) }, isError: false, isPaused: false,
});
const sina = () => ({ data: { data: [item("sina")], meta: meta({ limitations: [
  note("SINA_BOARD_BASIS"), note("FUND_FLOW_UNAVAILABLE"), note("SOURCE_SERVICE_TIME_ONLY"),
] }) }, isError: false, isPaused: false });

test("有效新浪榜优先于东财历史、失败和空榜；说明性partial不是请求失败", () => {
  const alternative = sina();
  assert.equal(availability.sectorFeedPriority(alternative), 0);
  for (const broken of [east({ status: "stale", cached: true }),
    { ...east(), isError: true }, { isError: true, isPaused: false },
    { ...east(), data: { data: [], meta: meta({ status: "empty" }) } }]) {
    assert.equal(availability.preferredSectorSource(broken, alternative), "sina");
  }
  assert.equal(availability.preferredSectorSource(east(), alternative), "eastmoney");
  assert.equal(availability.preferredSectorSource(east(), { ...alternative, isError: true }), "eastmoney");
  assert.equal(availability.preferredSectorSource(east(), { ...alternative, isPaused: true }), "eastmoney");
});

test("按所选分类判断可用性，未知限制仍影响优先级", () => {
  const alternative = sina();
  assert.equal(availability.sectorFeedPriority(alternative, "concept"), 3);
  assert.equal(availability.preferredSectorSource(east(), alternative, "concept"), "eastmoney");
  assert.equal(availability.sectorFeedPriority(east({ limitations: [note("NEW_UNKNOWN_LIMIT")] })), 1);
  assert.equal(availability.sectorFeedPriority(east({ limitations: [note("FUND_FLOW_UNAVAILABLE")] })), 1);
  assert.equal(availability.sectorFeedPriority(east({ limitations: [note("BOARD_CATALOG_QUOTE_MISSING")] })), 0);
});

const url = new URL("../components/macro/market-data-notice.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(url, "utf8"), { compilerOptions: {
  target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS,
} }).outputText;
const nativeRequire = createRequire(url);
const component = { exports: {} as { MarketDataNotice: (props: { meta?: MarketMeta; sectors: SectorItem[]; refreshError?: boolean; paused?: boolean }) => unknown } };
new Function("require", "module", "exports", compiled)((name: string) =>
  name === "@/lib/market-notice" ? notices : name === "@/lib/sector-availability" ? availability : nativeRequire(name), component, component.exports);
const render = (data: MarketMeta, source: SectorItem["source"] = "eastmoney", extra = {}) =>
  renderToStaticMarkup(createElement(component.exports.MarketDataNotice, { meta: data, sectors: [item(source)], ...extra }));
const outsideDetails = (html: string) => html.replace(/<details[\s\S]*?<\/details>/g, "");

test("历史状态与行情时间只提示一次，502与分类说明保留在默认折叠内", () => {
  const failure = note("BOARD_REFRESH_FAILED", "行业刷新失败：上游返回 HTTP 502");
  const html = render(meta({ status: "stale", cached: true, failed_sources: ["industry"], limitations: [
    note("BOARD_HISTORY_ONLY", "旧的重复历史提示"), note("BOARD_SNAPSHOT_MAY_BE_DELAYED", "旧的重复延迟提示"),
    failure, failure, note("BOARD_INDUSTRY_LEVELS_MIXED", "包含一级二级三级"),
    note("BOARD_CATALOG_QUOTE_MISSING", "BK1362无报价"),
  ] }));
  assert.equal((html.match(/HTTP 502/g) ?? []).length, 1);
  assert.match(outsideDetails(html), /更新暂不可用，显示上次行情/);
  assert.match(outsideDetails(html), /2026\/10\/26 15:39:30（北京时间）/);
  assert.doesNotMatch(outsideDetails(html), /502|BK1362|一级|缓存|历史快照|旧的重复/);
  assert.doesNotMatch(html, /<details[^>]* open/);
  assert.match(html, /bg-amber/);
});

test("正常快照和新浪说明用中性样式，仍标明报价时间边界", () => {
  const healthy = render(meta({ limitations: [note("BOARD_SNAPSHOT_MAY_BE_DELAYED")] }));
  assert.doesNotMatch(healthy, /bg-amber/);
  const html = render(sina().data.meta, "sina");
  assert.doesNotMatch(html, /bg-amber/);
  assert.match(outsideDetails(html), /已获取新浪榜单/);
  assert.match(outsideDetails(html), /服务更新时间：2026\/10\/26 15:01:54/);
  assert.match(outsideDetails(html), /来源未提供逐板块报价时间/);
  assert.doesNotMatch(outsideDetails(html), /FUND_FLOW_UNAVAILABLE|请求失败/);
});

test("刷新失败、离线与未知数据限制仍突出，缺失时间不会编造", () => {
  assert.match(outsideDetails(render(meta(), "eastmoney", { refreshError: true })), /更新暂不可用/);
  assert.match(outsideDetails(render(meta(), "eastmoney", { paused: true })), /网络已断开/);
  const html = render(meta({ limitations: [note("UNKNOWN", "新增数据异常")] }));
  assert.match(outsideDetails(html), /新增数据异常/);
  assert.match(html, /bg-amber/);
  assert.equal(availability.sectorTimeRange([{ ...item("eastmoney"), as_of: null }], "eastmoney"), "来源未提供");
  assert.match(availability.sectorTimeRange([item("eastmoney"), { ...item("eastmoney"), as_of: null }], "eastmoney"), /部分时间未提供/);
});

test("行业更新失败不会把成功的概念榜标成历史行情", () => {
  const mixed = east({ status: "stale", cached: true, failed_sources: ["industry"], limitations: [
    note("BOARD_HISTORY_ONLY"), note("BOARD_REFRESH_FAILED", "行业刷新失败：502"),
    note("BOARD_INDUSTRY_LEVELS_MIXED"), note("BOARD_CATALOG_QUOTE_MISSING"),
  ] });
  mixed.data.data.push({ ...item("eastmoney"), id: "BK0002", category: "concept" });
  const scoped = availability.sectorCategoryMeta(mixed.data.meta, "concept")!;
  assert.equal(availability.sectorFeedPriority(mixed, "concept"), 0);
  assert.equal(availability.sectorFeedPriority(mixed, "industry"), 2);
  assert.equal(availability.sectorFeedPriority(mixed), 2);
  assert.equal(scoped.status, "partial");
  assert.deepEqual(scoped.failed_sources, []);
  assert.deepEqual(scoped.limitations, []);
  assert.doesNotMatch(outsideDetails(render(scoped)), /更新暂不可用/);
  assert.equal(availability.sectorCategoryMeta(meta({ status: "stale", failed_sources: ["eastmoney"] }), "concept")!.status, "stale");
});
