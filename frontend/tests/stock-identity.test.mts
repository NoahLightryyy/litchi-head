import test from "node:test";
import assert from "node:assert/strict";
import { findStockIdentity, stockDisplayName } from "../lib/stock-identity.ts";

test("catalog identity survives unavailable quotes and matches exactly", () => {
  const identity = findStockIdentity("002885", [{ code: "002885", name: "京泉华", market: "sz" }]);
  assert.equal(stockDisplayName("002885", null, identity), "京泉华");
  for (const rows of [null, [], [{ code: "300750", name: "宁德时代" }],
    [{ code: "002885", name: " " }], [{ code: "002885", name: "002885" }],
    [{ code: "002885", name: "板块", type: "sector" }]]) {
    assert.equal(findStockIdentity("002885", rows), null);
  }
});

test("changing code never reuses another stock's quote or identity", () => {
  const old = { code: "002885", name: "京泉华" };
  assert.equal(stockDisplayName("300750", old, old), "300750");
  assert.equal(stockDisplayName("002885", { code: "002885", name: " " }, old), "京泉华");
  assert.equal(stockDisplayName("002885", { code: "002885", name: "京泉华新简称" }, old), "京泉华新简称");
});
