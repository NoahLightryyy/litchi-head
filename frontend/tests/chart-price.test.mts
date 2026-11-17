import test from "node:test";
import assert from "node:assert/strict";
import { candlePriceFields, priceSeriesFormat } from "../lib/chart-price.ts";
import { candleChange } from "../lib/chart-navigation.ts";

const candle = { date: "2026-10-26", open: 1.232, high: 1.239, low: 1.228, close: 1.235, volume: 100 };

test("ETF 三位报价和千分之一元涨跌不被两位格式吞掉，百分比保持两位", () => {
  const fields = candlePriceFields(candle, candleChange([1.234, candle.close], 1), "元", 3);
  assert.deepEqual([fields.open, fields.high, fields.low, fields.close], ["1.232", "1.239", "1.228", "1.235"]);
  assert.equal(fields.change, "+0.001 元  (+0.08%)");
  assert.deepEqual(priceSeriesFormat(3), { type: "price", precision: 3, minMove: 0.001 });
});

test("个股和指数保持默认两位，ETF 下跌与缺前收保留真实符号和缺项", () => {
  assert.equal(candlePriceFields(candle, null).close, "1.24");
  assert.equal(candlePriceFields(candle, null).change, "—");
  assert.equal(candlePriceFields(candle, null).baseline, "缺少前收盘价");
  assert.deepEqual(priceSeriesFormat(), { type: "price", precision: 2, minMove: 0.01 });
  assert.equal(candlePriceFields(candle, candleChange([1.236, candle.close], 1), "元", 3).change, "-0.001 元  (-0.08%)");
  assert.equal(candlePriceFields(candle, { amount: 0.12, percent: 0.03 }, "点").change, "+0.12 点  (+0.03%)");
});
