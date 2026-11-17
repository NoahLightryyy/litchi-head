import test from "node:test";
import assert from "node:assert/strict";
import {marketLimitationsView, MARKET_SOURCE_NOTICE} from "../lib/market-source-policy.ts";

test("only standalone legacy count warnings are retired; original is preserved", () => {
  const original = "行情为单源未交叉验证快照；未复权数据存在除权断点风险；短期方向缺乏量能确认，证据不足以给出明确方向。";
  const result = marketLimitationsView(original);
  assert.equal(result.text, "未复权数据存在除权断点风险；短期方向缺乏量能确认，证据不足以给出明确方向。");
  assert.equal(result.original, original); assert.equal(result.changed, true);
  assert.equal(marketLimitationsView("单源行情未交叉验证。").text, "无其他已记录限制。");
});
test("mixed risks, stale data, conflicting price and unsupported directions are never erased", () => {
  for (const text of ["单源报价存在时间过期与异常价格", "单源未交叉验证且存在价格冲突", "报价已过期", "短期证据不足", "价格冲突；除权断点", "来源数量不足，财务缺失"]) {
    assert.deepEqual(marketLimitationsView(text), {text, original:text, changed:false});
  }
  assert.match(MARKET_SOURCE_NOTICE, /旧评分与方向保持原样/);
});
