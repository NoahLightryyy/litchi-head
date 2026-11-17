import assert from "node:assert/strict";
import test from "node:test";
import { formatQuoteOptionalNumber, formatQuoteTime, quoteSourceLabel } from "../lib/quote-display.ts";

test("unknown enrichment is distinct from zero and negative amounts keep their sign", () => {
  assert.equal(formatQuoteOptionalNumber(null, 2, "%"), "—");
  assert.equal(formatQuoteOptionalNumber(0, 2, "%"), "0.00%");
  assert.equal(formatQuoteOptionalNumber(-2, 1, "亿", true), "-2.0亿");
});

test("quote timestamp keeps the trading date and Shanghai timezone", () => {
  assert.match(formatQuoteTime("2026-09-30T07:30:00Z"), /2026\/09\/30 15:30:00/);
});


test("all three display quote sources have human-readable labels", () => {
  assert.equal(quoteSourceLabel("tencent"), "腾讯");
  assert.equal(quoteSourceLabel("sina"), "新浪");
  assert.equal(quoteSourceLabel("eastmoney"), "东方财富");
  assert.equal(quoteSourceLabel(), "行情来源");
});
