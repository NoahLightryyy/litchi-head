import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryObserver } from "@tanstack/react-query";
import ts from "typescript";
import { parseEtfKline, requireEtfKline, type EtfKline } from "../lib/etf-kline.ts";
import * as etfKline from "../lib/etf-kline.ts";
import * as periods from "../lib/raw-period.ts";

const fixture = (): EtfKline => ({
  schema_version: 1, identity: { code: "560780", symbol: "sh560780", exchange: "SH", name: "半导体设备ETF广发", instrument_type: "etf" },
  status: "ready", source: "tencent", price_basis: "raw", price_unit: "CNY", price_tick: 0.001,
  volume_unit: "fund_units", verification: "single_source", fetched_at: "2026-10-27T08:00:00+08:00",
  requested_start: "2024-10-27", requested_end: "2026-10-26", data_start: "2026-10-23", data_end: "2026-10-26",
  bars: [
    { date: "2026-10-23", open: 0.788, high: 0.791, low: 0.777, close: 0.781, volume: 1234567 },
    { date: "2026-10-26", open: 0.781, high: 0.790, low: 0.747, close: 0.749, volume: 516826000 },
  ], diagnostics: [{ source: "tencent", status: "success", error_code: null }], limitations: ["单源不复权交易价格，不代表净值"],
});

test("ETF 日线保留三位价格和份额，不因新上市短序列拒绝有效来源", () => {
  const data = parseEtfKline(fixture(), "560780");
  assert.equal(data.bars[1].close, 0.749);
  assert.equal(data.bars[1].volume, 516826000);
  const fallback = { ...fixture(), source: "sina" as const, diagnostics: [
    { source: "tencent" as const, status: "failed" as const, error_code: "upstream_request_failed" },
    { source: "sina" as const, status: "success" as const, error_code: null },
  ] };
  assert.equal(requireEtfKline(fallback, "560780").status, "ready");
  assert.equal(parseEtfKline({ ...fixture(), data_start: "2026-10-26", bars: [fixture().bars[1]] }, "560780").bars.length, 1);
});

test("拒绝错基金、复权或成交量单位、坏 OHLC、重复日和未来行情", () => {
  for (const replacement of [
    { identity: { ...fixture().identity, code: "159915" } }, { identity: { ...fixture().identity, instrument_type: "stock" } },
    { identity: { ...fixture().identity, exchange: "SZ" } }, { price_basis: "qfq" }, { volume_unit: "lots" }, { price_tick: 0.01 },
    { source: null }, { status: "empty" }, { fetched_at: "2026-10-27T08:00:00" }, { data_end: "2026-10-25" },
    { requested_end: "2026-10-28" }, { bars: [fixture().bars[0], fixture().bars[0]] },
  ]) assert.throws(() => parseEtfKline({ ...fixture(), ...replacement }, "560780"));
  for (const replacement of [{ close: 0.7495 }, { high: 0.1 }, { low: 2 }, { volume: 100.5 }, { volume: -1 }, { date: "2026-02-30" }]) {
    assert.throws(() => parseEtfKline({ ...fixture(), bars: [{ ...fixture().bars[0], ...replacement }, fixture().bars[1]] }, "560780"));
  }
});

test("历史源不可用保留同ETF旧图，确实空数据与基金切换清空旧序列", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  let response = fixture();
  const options = (code = "560780") => ({ queryKey: ["etf", code, "kline", 730], queryFn: async () => requireEtfKline(response, code) });
  try {
    await client.fetchQuery(options());
    const observer = new QueryObserver(client, options());
    response = { ...fixture(), status: "unavailable", source: null, bars: [], data_start: null, data_end: null };
    const failed = await observer.refetch();
    assert.equal(failed.isError, true); assert.equal(failed.data?.bars[1].close, 0.749);
    response = { ...response, status: "empty" };
    assert.equal((await observer.refetch()).data?.bars.length, 0);
    observer.setOptions(options("159915"));
    assert.equal(observer.getCurrentResult().data, undefined);
    observer.destroy();
  } finally { client.clear(); }
});

const componentUrl = new URL("../components/etf/etf-kline-panel.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(componentUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const componentModule = { exports: {} as { EtfKlineContent: (props: never) => unknown } };
const require = createRequire(componentUrl);
new Function("require", "module", "exports", compiled)((name: string) => {
  if (name === "@/lib/api/client") return {};
  if (name === "@/lib/etf-kline") return etfKline;
  if (name === "@/lib/raw-period") return periods;
  if (name === "@/components/stock/candlestick-chart") return {
    CandlestickChart: (props: { data: { close: number }[]; pricePrecision: number; volumeLabel: string }) => createElement("div", { "aria-label": "test-chart" }, `${props.pricePrecision}位 ${props.volumeLabel} ${props.data.length}根 ${props.data.at(-1)?.close}`),
  };
  return require(name);
}, componentModule, componentModule.exports);
const render = (props: { data?: EtfKline; pending?: boolean; failed?: boolean; paused?: boolean; error?: string; period?: periods.DisplayPeriod } = {}) => renderToStaticMarkup(createElement(componentModule.exports.EtfKlineContent, { pending: false, failed: false, paused: false, period: "daily", ...props } as never));

test("图表注明ETF单位日期，使用三位精度；周月线聚合但不伪造新报价", () => {
  const daily = render({ data: fixture() });
  assert.match(daily, /腾讯 · 不复权 · 成交量单位：份/);
  assert.match(daily, /3位 成交量（份） 2根 0.749/);
  assert.match(daily, /2026-10-23 — 2026-10-26/);
  assert.match(daily, /非基金净值/);
  assert.match(daily, /当前来源日线截至 2026-10-26/);
  assert.doesNotMatch(daily, /不含今日行情/);
  const monthly = render({ data: fixture(), period: "monthly" });
  assert.match(monthly, /1 根月线/);
  assert.match(monthly, /首尾周期可能不完整/);
  assert.match(monthly, /3位 成交量（份） 1根 0.749/);
  assert.match(render({ pending: true }), /正在读取 ETF 历史行情/);
  assert.match(render({ data: fixture(), failed: true }), /保留上次成功的图表/);
  assert.match(render({ data: fixture(), paused: true }), /保留上次取得的历史行情/);
  assert.match(render({ data: { ...fixture(), status: "empty", bars: [], source: null, data_start: null, data_end: null } }), /暂无 ETF 日线/);
});


const todayFixture = (fetched_at: string): EtfKline => ({
  ...fixture(), fetched_at, requested_end: "2026-10-27", data_end: "2026-10-27",
  bars: [...fixture().bars, { ...fixture().bars[1], date: "2026-10-27", close: 0.780 }],
});

test("北京时间今日已获日线可画图，未来日仍拒绝", () => {
  for (const stamp of ["2026-10-27T10:30:00+08:00", "2026-10-27T15:35:00+08:00", "2026-10-26T16:30:00Z"]) {
    const result = parseEtfKline(todayFixture(stamp), "560780");
    assert.equal(result.bars.length, 3);
    assert.equal(result.data_end, "2026-10-27");
  }
  assert.throws(() => parseEtfKline(todayFixture("2026-10-26T15:59:59Z"), "560780"));
});

test("盘中蜡烛标识未收盘，周月线包括当天但说明周期未完", () => {
  const data = todayFixture("2026-10-27T14:59:59+08:00");
  for (const period of ["daily", "weekly", "monthly"] as const) {
    const markup = render({ data, period });
    assert.match(markup, /2026-10-27 当日日线（采集时尚未收盘）/);
    assert.match(markup, /收盘价栏为当时最新价/);
    assert.match(markup, /0.78/);
    if (period !== "daily") assert.match(markup, /首尾周期可能不完整/);
  }
});

test("采集时点决定盘中盘后标识，旧缓存不会因本机已收盘而改标签", () => {
  const intraday = todayFixture("2026-10-27T06:59:59Z");
  const afterClose = todayFixture("2026-10-27T07:00:00Z");
  assert.match(render({ data: afterClose }), /已含 2026-10-27 当日日线（收盘后采集）/);
  assert.doesNotMatch(render({ data: afterClose }), /采集时尚未收盘/);
  const failed = render({ data: intraday, failed: true });
  assert.match(failed, /保留上次成功的图表/);
  assert.match(failed, /采集时尚未收盘/);
  assert.doesNotMatch(failed, /收盘后采集/);
});
