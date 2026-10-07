import test from "node:test";
import assert from "node:assert/strict";
import {selectDebateView} from "../lib/debate-history.ts";
const records = [
  {session_id:"other",stock_code:"000001",status:"completed"},
  {session_id:"running",stock_code:"920344",status:"running"},
  {session_id:"new",stock_code:"920344",status:"completed"},
  {session_id:"old",stock_code:"920344",status:"completed"},
];
test("刷新时恢复该股最近完整历史，排除其他股票和未完成结果", () => {
  assert.deepEqual(selectDebateView(records,"920344",null,null,false),{sessionId:"new",historical:true});
});
test("新分析或失败后不把旧结论冒充本次结果，用户仍可主动查看历史", () => {
  assert.deepEqual(selectDebateView(records,"920344",null,null,true),{sessionId:null,historical:false});
  assert.deepEqual(selectDebateView(records,"920344",null,"current",true),{sessionId:"current",historical:false});
  assert.deepEqual(selectDebateView(records,"920344","old",null,true),{sessionId:"old",historical:true});
  assert.deepEqual(selectDebateView(records,"920344","other",null,true),{sessionId:null,historical:false});
});
