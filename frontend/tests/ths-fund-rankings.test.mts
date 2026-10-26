import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryObserver, onlineManager } from "@tanstack/react-query";
import ts from "typescript";
import { rankingPage } from "../lib/ranking-page.ts";
import {
  parseThsFundResult, requireThsFundData, thsFundQueryPolicy,
  type ThsFundPeriod, type ThsFundResult,
} from "../lib/ths-fund-rankings.ts";

const fixture = (period: ThsFundPeriod = "latest"): ThsFundResult => ({
  source: "ths", metric: "net_inflow", period, unit: "CNY", status: "partial",
  data: [
    { code: "600000", name: "测试股票", price: 10.5, net_inflow: 123456789 },
    { code: "000001", name: "测试负值", price: null, net_inflow: -10000 },
  ],
  data_as_of: null, fetched_at: "2026-10-26T16:30:00+08:00", cached: false,
  scope: "同花顺沪深个股资金净流入降序前50项；不等同东方财富主力净流入",
  reason: "来源未提供数据日期及统计截止日；采集时间不代表行情时间。",
});

test("同花顺独立契约拒绝混源、主力口径、单位和周期错配", () => {
  assert.equal(parseThsFundResult(fixture(), "latest").data[1].net_inflow, -10000);
  for (const replacement of [
    { source: "eastmoney" }, { metric: "main_net" }, { metric: "gross_in" },
    { period: "3" }, { unit: "万元" }, { cached: "false" }, { status: "ready" },
  ]) assert.throws(() => parseThsFundResult({ ...fixture(), ...replacement }, "latest"));
  for (const period of ["previous", "60", "unknown"]) {
    assert.throws(() => parseThsFundResult({ ...fixture(), period }, period as ThsFundPeriod));
  }
  for (const value of [null, [], "data"]) assert.throws(() => parseThsFundResult(value, "latest"));
});

test("时间缺失不能被采集时间伪装，采集时间必须携带时区", () => {
  for (const replacement of [
    { data_as_of: "2026-10-26" }, { data_as_of: "2026-10-26T15:00:00+08:00" },
    { data_as_of: undefined }, { fetched_at: "2026-10-26T16:30:00" }, { fetched_at: "invalid" },
  ]) assert.throws(() => parseThsFundResult({ ...fixture(), ...replacement }, "latest"));
});

test("金额、排序、身份和失败响应均严格校验", () => {
  for (const net_inflow of [NaN, Infinity, -Infinity, "123", null]) {
    const value = fixture();
    assert.throws(() => parseThsFundResult({ ...value, data: [{ ...value.data[0], net_inflow }] }, "latest"));
  }
  for (const replacement of [{ price: 0 }, { price: -1 }, { price: Infinity }, { name: " " }, { code: 600000 }, { code: "60000" }]) {
    const value = fixture();
    assert.throws(() => parseThsFundResult({ ...value, data: [{ ...value.data[0], ...replacement }] }, "latest"));
  }
  const value = fixture();
  assert.throws(() => parseThsFundResult({ ...value, data: [...value.data].reverse() }, "latest"));
  assert.throws(() => parseThsFundResult({ ...value, data: [value.data[0], value.data[0]] }, "latest"));
  assert.throws(() => parseThsFundResult({ ...value, status: "unavailable" }, "latest"));
  assert.throws(() => parseThsFundResult({ ...value, data: [] }, "latest"));
  const unavailable = { ...value, status: "unavailable", data: [] };
  assert.equal(parseThsFundResult(unavailable, "latest").data.length, 0);
  assert.throws(() => requireThsFundData(unavailable, "latest"));
});

test("刷新返回不可用时保留上次同周期数据，换周期不复用旧榜", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
  let response = fixture();
  const options = (period: ThsFundPeriod) => ({
    queryKey: ["discovery", "fund-flow", "ths", period], ...thsFundQueryPolicy,
    queryFn: async () => requireThsFundData(response, period),
  });
  try {
    const original = await client.fetchQuery(options("latest"));
    const observer = new QueryObserver(client, options("latest"));
    response = { ...fixture(), status: "unavailable", data: [] };
    const result = await observer.refetch();
    assert.equal(result.isError, true);
    assert.deepEqual(result.data, original);
    observer.setOptions(options("3"));
    assert.equal(observer.getCurrentResult().data, undefined);
    assert.equal(observer.getCurrentResult().isPending, true);
    observer.destroy();
  } finally { client.clear(); }
});

test("离线读取暂停，联网后自动恢复", async () => {
  const client = new QueryClient();
  client.mount();
  onlineManager.setOnline(false);
  let calls = 0;
  const observer = new QueryObserver(client, {
    queryKey: ["discovery", "fund-flow", "ths", "latest"], ...thsFundQueryPolicy,
    queryFn: async () => { calls++; return requireThsFundData(fixture(), "latest"); },
  });
  const stop = observer.subscribe(() => {});
  try {
    assert.equal(observer.getCurrentResult().fetchStatus, "paused");
    assert.equal(calls, 0);
    onlineManager.setOnline(true);
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(calls, 1);
    assert.equal(observer.getCurrentResult().data?.source, "ths");
  } finally { stop(); observer.destroy(); client.unmount(); client.clear(); onlineManager.setOnline(true); }
});

// Render the actual view, keeping date and unit assertions tied to user-visible text.
const componentUrl = new URL("../components/shared/ths-fund-ranking-content.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(componentUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
type ViewProps = { data?: ThsFundResult; pending: boolean; failed: boolean; paused: boolean };
const componentModule = { exports: {} as { ThsFundRankingContent: (props: ViewProps) => unknown } };
const paginationUrl = new URL("../components/shared/ranking-pagination.tsx", import.meta.url);
const paginationModule = { exports: {} };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(paginationUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText)(createRequire(paginationUrl), paginationModule, paginationModule.exports);
new Function("require", "module", "exports", compiled)((id: string) => {
  if (id === "@/lib/ranking-page") return { rankingPage };
  if (id === "./ranking-pagination") return paginationModule.exports;
  return createRequire(componentUrl)(id);
}, componentModule, componentModule.exports);
const render = (props: Partial<ViewProps> = {}) => renderToStaticMarkup(createElement(componentModule.exports.ThsFundRankingContent, {
  pending: false, failed: false, paused: false, ...props,
}));

test("页面把采集时间与缺失的数据日期分开，并正确显示万元和负值", () => {
  const html = render({ data: fixture() });
  assert.match(html, /数据日期：来源未提供/);
  assert.match(html, /采集时间（北京时间）：/);
  assert.match(html, /不代表报价时间或统计截止日/);
  assert.match(html, /资金净流入（万元）/);
  assert.match(html, /\+12,345\.68/);
  assert.match(html, /-1\.00/);
  assert.match(html, /—/);
  assert.doesNotMatch(html, /统计交易日：|报价时间（北京时间）|已核验/);
});

test("加载、空数据、失败、离线均明确展示，失败刷新不隐藏旧表", () => {
  assert.match(render({ pending: true }), /正在读取同花顺资金榜/);
  assert.match(render(), /该周期暂无可展示/);
  assert.match(render({ failed: true }), /当前未取得同花顺资金净流入榜/);
  assert.match(render({ paused: true, pending: true }), /网络已断开/);
  for (const state of [{ failed: true }, { paused: true }]) {
    const html = render({ data: fixture(), ...state });
    assert.match(html, /保留上次获取的本周期榜单/);
    assert.match(html, /测试股票/);
  }
  const cached = render({ data: { ...fixture(), cached: true, reason: "刷新未成功，保留上次采集数据。" } });
  assert.match(cached, /刷新未成功，保留上次采集数据/);
  assert.match(cached, /测试股票/);
  const failedPayload = render({ data: { ...fixture(), status: "unavailable" } });
  assert.doesNotMatch(failedPayload, /测试股票/);
});

test("资金榜首次仅展示10条，失败保留榜单也按页展示", () => {
  const data = { ...fixture(), data: Array.from({ length: 21 }, (_, i) => ({
    code: String(600000 + i), name: `排行股票${i + 1}`, price: 10, net_inflow: 210000 - i * 10000,
  })) };
  for (const failed of [false, true]) {
    const html = render({ data, failed });
    assert.equal((html.match(/href="\/stock\//g) ?? []).length, 10);
    assert.match(html, /排行股票10/);
    assert.doesNotMatch(html, /排行股票11/);
    assert.match(html, /第 1 \/ 3 页/);
    assert.match(html, /disabled="">上一页/);
    assert.doesNotMatch(html, /disabled="">下一页/);
  }
  assert.doesNotMatch(render(), /aria-label="同花顺资金净流入分页"/);
});
