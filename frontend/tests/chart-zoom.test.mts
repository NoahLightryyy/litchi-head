import type { IChartApi } from "lightweight-charts";
import assert from "node:assert/strict";
import test from "node:test";
import { boundaryIntent, stepPriceWindow, bindChartZoom } from "../lib/chart-zoom.ts";
import { parseFiveDay } from "../lib/five-day-display.ts";

test("时间层级双向切换并在两端停止", () => {
  assert.equal(stepPriceWindow("intraday", "out"), "five-day");
  assert.equal(stepPriceWindow("five-day", "out"), "daily");
  assert.equal(stepPriceWindow("daily", "out"), "daily");
  assert.equal(stepPriceWindow("daily", "in"), "five-day");
  assert.equal(stepPriceWindow("five-day", "in"), "intraday");
  assert.equal(stepPriceWindow("intraday", "in"), "intraday");
});
test("连续惯性不跨两层，停止后新手势允许切换", () => {
  const gate = {lastEvent: 0, switched: false, overscroll: 0};
  assert.equal(boundaryIntent(gate, 100, 1000), true);
  gate.switched = true;
  assert.equal(boundaryIntent(gate, 100, 1100), false);
  assert.equal(boundaryIntent(gate, 100, 1200), false);
  assert.equal(boundaryIntent(gate, 100, 1501), true);
});
test("滚轮越界切换模式，日K放大返回五日，平移旧日不误切", () => {
  let listener: (e: WheelEvent) => void = () => { throw new Error("not attached"); };
  let out = 0, into = 0;
  let range = {from: 0, to: 99};
  const chart = {timeScale: () => ({getVisibleLogicalRange: () => range,
    fitContent: () => {}, setVisibleLogicalRange: (v: {from: number; to: number}) => {range = v;}})};
  const element = {addEventListener: (_: string, f: (e: WheelEvent) => void) => {listener = f;}, removeEventListener: () => {}};
  const gesture = {lastEvent: 0, switched: false, overscroll: 0};
  const cleanup = bindChartZoom(chart as unknown as IChartApi, element as unknown as HTMLElement, 100, {gesture: {current: gesture}, onOut: () => out++, onIn: () => into++});
  const send = (deltaY: number) => listener({deltaY, deltaX: 0, deltaMode: 0, preventDefault() {}, stopPropagation() {}} as WheelEvent);
  send(120); send(120); assert.equal(out, 1);
  gesture.switched = false; range = {from: 0, to: 98.5}; send(-150);
  assert.equal(range.to, 99.5, "最新窗口缩放始终锚定最后一根K线");
  gesture.switched = false; range = {from: 90, to: 99}; send(-150); assert.equal(into, 1);
  gesture.switched = false; range = {from: 10, to: 19}; send(-150); assert.equal(into, 1);
  assert.ok(range.from >= 0 && range.to < 100); cleanup();
});
test("五日契约拒绝错股票、重复点、缺交易日身份和冒充已核验", () => {
  const v = {symbol: "300199", source: "tencent", price_basis: "unverified_raw", verification: "single_source",
    status: "partial", fetched_at: "2026-10-01T10:00:00+08:00", days: ["2026-09-30"],
    points: [{timestamp: "2026-09-30T09:30:00+08:00", close: 23}], incomplete_days: ["2026-09-30"], missing_days: [], error_code: null};
  assert.equal(parseFiveDay(v, "300199").points.length, 1);
  for (const bad of [{...v, symbol: "000001"}, {...v, points: [...v.points, ...v.points]},
    {...v, days: []}, {...v, verification: "verified"}, {...v, points: [{...v.points[0], close: NaN}]}]) {
    assert.throws(() => parseFiveDay(bad, "300199"));
  }
});
