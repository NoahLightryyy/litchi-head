import assert from "node:assert/strict";
import test from "node:test";
import { intradayReferenceClose, formatIntradayPercent } from "../lib/intraday-percent.ts";
const quote = { code: "300893", prev_close: 12.76, fetched_at: "2026-09-30T15:00:00+08:00" };
const points = [{timestamp: "2026-09-30T09:30:00+08:00"}, {timestamp: "2026-09-30T07:30:00Z"}];
test("休市可用同交易日昨收；金额与百分比同基准", () => {
  assert.equal(intradayReferenceClose("300893", quote, points), 12.76);
  assert.equal(formatIntradayPercent(15.13, 12.76), "+18.57%");
  assert.equal(formatIntradayPercent(12.76, 12.76), "0.00%");
  assert.equal(formatIntradayPercent(9, 10), "-10.00%");
  assert.equal(formatIntradayPercent(9.999999, 10), "0.00%");
});
test("拒绝错身份、日期、跨日、无时区和非法昨收", () => {
  assert.equal(intradayReferenceClose("920344", quote, points), null);
  assert.equal(intradayReferenceClose("300893", {...quote, fetched_at: "2026-10-01T15:00:00+08:00"}, points), null);
  assert.equal(intradayReferenceClose("300893", quote, [...points, {timestamp:"2026-09-29T15:00:00+08:00"}]), null);
  assert.equal(intradayReferenceClose("300893", {...quote, fetched_at:"2026-09-30T15:00:00"}, points), null);
  for (const prev_close of [0, -1, NaN, Infinity]) {
    assert.equal(intradayReferenceClose("300893", {...quote, prev_close}, points), null);
    assert.equal(formatIntradayPercent(15, prev_close), "—");
  }
  assert.equal(intradayReferenceClose("300893", null, points), null);
  assert.equal(intradayReferenceClose("300893", quote, []), null);
});
