import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as technical from "../lib/technical-summary.ts";
import type { CandleInput } from "../lib/chart-indicators.ts";

const bars = (count: number, up = true): CandleInput[] => Array.from({ length: count }, (_, i) => ({
  date: new Date(Date.UTC(2026, 0, i + 1)).toISOString().slice(0, 10), open: up ? i + 1 : 100 - i, high: up ? i + 1 : 100 - i, low: up ? i + 1 : 100 - i, close: up ? i + 1 : 100 - i, volume: 100,
}));
test("不足60根也计算可用均线；不把预热期填成0", () => {
  const short = technical.rawTechnicalSummary(bars(10))!;
  assert.equal(short.ma.ma5, 8); assert.equal(short.ma.ma10, 5.5);
  assert.equal(short.ma.ma60, null); assert.equal(short.rsi, null); assert.equal(short.macd.signal, null);
  assert.equal(technical.rawTechnicalSummary([]), null);
});
test("短期均线高于长期才是多头；下跌、横盘和缺样本不反向判断", () => {
  assert.equal(technical.movingAverageOrder(technical.rawTechnicalSummary(bars(70))!.ma), "bullish");
  assert.equal(technical.movingAverageOrder(technical.rawTechnicalSummary(bars(70, false))!.ma), "bearish");
  assert.equal(technical.movingAverageOrder({ ma5: 10, ma10: 10, ma20: 10, ma60: 10 }), "mixed");
  assert.equal(technical.movingAverageOrder({ ma5: 10, ma10: null, ma20: null, ma60: null }), "insufficient");
});
let primary: Record<string, unknown> = {}, fallback: Record<string, unknown> = {};
const component = new URL("../components/stock/technical-indicators-panel.tsx", import.meta.url);
const loaded = { exports: {} as { TechnicalIndicatorsPanel: (props: { code: string }) => ReturnType<typeof createElement> } };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(component, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)((id: string) => {
  if (id === "@/lib/hooks/use-stock") return { useTechnicalIndicators: () => primary };
  if (id === "@/lib/hooks/use-raw-daily") return { useRawDaily: () => fallback };
  if (id === "@/lib/technical-summary") return technical;
  return createRequire(component)(id);
}, loaded, loaded.exports);
const render = () => renderToStaticMarkup(createElement(loaded.exports.TechnicalIndicatorsPanel, { code: "300750" }));
test("主来源空时展示已取得的图表日线指标、时间和不复权口径", () => {
  primary = { data: null }; fallback = { data: { bars: bars(70), end: "2026-03-11" } };
  const html = render();
  for (const text of ["图表的备用日线", "腾讯", "不复权", "70", "2026-03-11", "多头排列", "68.00"]) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /需要至少 60|暂无技术指标数据/);
  primary = { isFetching: true }; assert.match(render(), /68.00/);
  fallback.isError = true; assert.match(render(), /更新未成功，保留上述日期/);
});
test("主指标可用时不混入备用价格口径；双失败、离线和加载分别说明", () => {
  primary = { data: technical.rawTechnicalSummary(bars(70, false)) }; fallback = { data: { bars: bars(70), end: "2026-03-11" } };
  assert.match(render(), /空头排列/); assert.doesNotMatch(render(), /腾讯/);
  primary = { isError: true }; fallback = { isError: true };
  assert.match(render(), /并非这只股票没有历史数据/);
  primary.fetchStatus = "paused"; assert.match(render(), /当前离线/);
  primary = { isFetching: true }; assert.match(render(), /animate-pulse/);
});
