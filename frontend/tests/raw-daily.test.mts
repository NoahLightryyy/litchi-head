import test from "node:test";
import assert from "node:assert/strict";
import { parseRawDaily } from "../lib/raw-daily.ts";
const bar = {code:"300913",price_basis:"raw",period:"1d",trade_date:"2026-09-18",open:"40",high:"42",low:"39",close:"41",volume:100};
const payload = {symbol:"300913",source:"tencent",price_basis:"raw",verification:"single_source",status:"success_data",data_start:"2026-09-18",data_end:"2026-09-18",bars:[bar]};
test("备用图表解析价格字符串且拒绝错误身份、口径、排序和OHLC", () => {
  assert.equal(parseRawDaily(payload,"300913").bars[0].close,41);
  assert.throws(()=>parseRawDaily(payload,"000001"));
  assert.throws(()=>parseRawDaily({...payload,price_basis:"qfq"},"300913"));
  assert.throws(()=>parseRawDaily({...payload,bars:[bar,bar]},"300913"));
  assert.throws(()=>parseRawDaily({...payload,bars:[{...bar,high:"0"}]},"300913"));
  assert.throws(()=>parseRawDaily({...payload,status:"failed"},"300913"));
});
