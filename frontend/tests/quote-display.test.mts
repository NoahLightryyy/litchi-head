import assert from "node:assert/strict";
import test from "node:test";
import { formatQuoteOptionalNumber, formatQuoteTime } from "../lib/quote-display.ts";

test("unknown enrichment is distinct from zero and negative amounts keep their sign", () => {
  assert.equal(formatQuoteOptionalNumber(null, 2, "%"), "—");
  assert.equal(formatQuoteOptionalNumber(0, 2, "%"), "0.00%");
  assert.equal(formatQuoteOptionalNumber(-2, 1, "亿", true), "-2.0亿");
});

test("quote timestamp keeps the trading date and Shanghai timezone", () => {
  assert.match(formatQuoteTime("2026-09-30T07:30:00Z"), /2026\/09\/30 15:30:00/);
});
