import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient } from "@tanstack/react-query";
import ts from "typescript";
import * as recovery from "../lib/intraday-recovery.ts";
import * as states from "../lib/intraday-source-state.ts";
import * as percent from "../lib/intraday-percent.ts";
import * as five from "../lib/five-day-display.ts";
import * as identity from "../lib/stock-identity.ts";
import type { IntradayBattlefield } from "../lib/types/stock.ts";

function compile(file: string, mocks: Record<string, unknown>) {
  const url = new URL(file, import.meta.url), require = createRequire(url);
  const code = ts.transpileModule(readFileSync(url, "utf8"), {compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  }}).outputText;
  const mod = {exports: {} as Record<string, unknown>};
  new Function("require", "module", "exports", code)((name: string) => name in mocks ? mocks[name] : require(name), mod, mod.exports);
  return mod.exports;
}
const stamp = "2026-10-27T15:00:00+08:00";
const unavailable = {symbol: "002885", usable: false, price_points: [], verification_status: "unavailable", as_of: null,
  source_diagnostics: [{source_id: "direct-tencent-intraday", source_name: "腾讯", status: "failed", fetched_at: stamp,
    error_code: "upstream_request_failed", error_message: "HTTP 501", checkpoint_count: 0}], available_source_ids: []} as unknown as IntradayBattlefield;
const good = {...unavailable, usable: true, price_points: [{timestamp: stamp, close: 20.10}], verification_status: "single_source",
  canonical_source_id: "direct-tencent-intraday", as_of: stamp, snapshot: null} as IntradayBattlefield;
const history = {symbol: "002885", source: "tencent", verification: "single_source", price_basis: "unverified_raw", status: "partial",
  fetched_at: stamp, days: ["2026-10-27"], points: [{timestamp: stamp, close: 20.10}], incomplete_days: [], missing_days: [], error_code: null} as five.FiveDayDisplay;

function panel(primary: object, backup: object) {
  const Component = compile("../components/stock/intraday-battlefield-panel.tsx", {
    "@/lib/hooks/use-stock": {useIntradayBattlefield: () => primary, useStockQuote: () => ({data: undefined})},
    "@/lib/hooks/use-five-day-display": {useFiveDayDisplay: () => backup},
    "@/lib/intraday-source-state": states, "@/lib/intraday-percent": percent, "@/lib/intraday-recovery": recovery,
    "@/lib/chart-zoom": {stepPriceWindow: () => "daily"},
    "./five-day-chart": {FiveDayChart: () => createElement("p", null, "FIVE_DAY")},
    "./kline-chart": {KlineChart: () => createElement("p", null, "DAILY_CHART")},
    "@/components/stock/intraday-line-chart": {IntradayLineChart: (p: {points: {close: number}[]}) => createElement("p", {"data-chart": "minute"}, p.points.map(x => x.close).join(","))},
  }).IntradayBattlefieldPanel as (p: {code: string}) => ReactElement;
  return renderToStaticMarkup(createElement(Component, {code: "002885"}));
}
const primaryFailure = {error: new recovery.IntradayUnavailableError(unavailable), isError: true, isLoading: false, isFetching: false};

test("panel renders alternate minutes, actual date and the original transport diagnosis", () => {
  const html = panel(primaryFailure, {data: history, isPending: false, isError: false});
  assert.match(html, /备用分时 · 腾讯/); assert.match(html, /五日记录中的/); assert.match(html, /2026-10-27/);
  assert.match(html, /data-chart="minute">20.1/); assert.match(html, /HTTP 501/);
  assert.doesNotMatch(html, /本地结构与时间校验|DAILY_CHART|VWAP|累计成交量/);
});

test("pending backup keeps loading; both paths failing selects and renders daily", () => {
  const pending = panel(primaryFailure, {isPending: true});
  assert.match(pending, /正在尝试备用分钟记录/); assert.doesNotMatch(pending, /DAILY_CHART/);
  const failed = panel(primaryFailure, {isPending: false, isError: true});
  assert.match(failed, /aria-pressed="true"[^>]*>日 K/); assert.match(failed, /DAILY_CHART/);
});

test("cached primary survives an empty 200 with new failure details, not fictitious success", () => {
  const html = panel({...primaryFailure, data: good}, {isPending: true});
  assert.match(html, /刷新失败/); assert.match(html, /2026\/10\/27/); assert.match(html, /data-chart="minute">20.1/);
  assert.match(html, /HTTP 501/); assert.doesNotMatch(html, /DAILY_CHART/);
});

test("backup refresh failure keeps dated minutes and says it is the last saved record", () => {
  assert.match(panel(primaryFailure, {data: history, isPending: false, isError: true}), /备用分时刷新未成功，保留上次记录/);
});

test("real query cache retains last success after an unusable 200 and isolates stock keys", async () => {
  let response = good;
  const options = compile("../lib/hooks/use-stock.ts", {
    "@tanstack/react-query": {useQuery: (options: unknown) => options},
    "@/lib/api/stocks": {fetchIntradayBattlefield: async () => response},
    "@/lib/intraday-recovery": recovery, "@/lib/stock-identity": identity,
    "./use-debounce": {useDebounce: (v: string) => v},
  }).useIntradayBattlefield as (code: string) => {queryKey: string[]; queryFn: (context: {signal: AbortSignal}) => Promise<IntradayBattlefield>; retry: false};
  const client = new QueryClient({defaultOptions: {queries: {retry: false, gcTime: 0}}});
  const config = {...options("002885"), staleTime: 0};
  try {
    assert.equal(config.retry, false);
    await client.fetchQuery(config);
    response = unavailable;
    await assert.rejects(client.fetchQuery(config), recovery.IntradayUnavailableError);
    assert.equal(client.getQueryData(config.queryKey), good);
    assert.equal(client.getQueryState(config.queryKey)?.status, "error");
    await assert.rejects(client.fetchQuery({...options("300750"), staleTime: 0}));
    assert.equal(client.getQueryData(options("300750").queryKey), undefined);
  } finally {client.clear();}
});

test("current-session fallback and five-day view share one bounded query and reject empty refresh", async () => {
  let result: unknown = history;
  const hook = compile("../lib/hooks/use-five-day-display.ts", {
    "@tanstack/react-query": {useQuery: (options: unknown) => options},
    "@/lib/api/client": {api: {getRaw: async () => result}}, "@/lib/five-day-display": five,
  }).useFiveDayDisplay as (code: string, enabled?: boolean) => {queryKey: string[]; queryFn: (context: {signal: AbortSignal}) => Promise<unknown>; enabled: boolean; retry: boolean};
  const enabled = hook("002885"), disabled = hook("002885", false);
  assert.deepEqual(enabled.queryKey, disabled.queryKey); assert.equal(disabled.enabled, false); assert.equal(enabled.retry, false);
  assert.equal(await enabled.queryFn({signal: new AbortController().signal}), history);
  result = {...history, status: "failed", points: [], days: []};
  await assert.rejects(enabled.queryFn({signal: new AbortController().signal}));
});

test("minute reference source reuses the three-vendor quote label rather than a two-vendor whitelist", () => {
  const source = readFileSync(new URL("../components/stock/intraday-line-chart.tsx", import.meta.url), "utf8");
  assert.match(source, /quoteSourceLabel\(reference\?\.source\)/);
  assert.doesNotMatch(source, /"报价源"/);
});
