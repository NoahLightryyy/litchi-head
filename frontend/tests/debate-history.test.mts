import test from "node:test";
import assert from "node:assert/strict";
import {selectDebateView} from "../lib/debate-history.ts";
const records = [
  {session_id:"other",stock_code:"000001",status:"completed"},
  {session_id:"running",stock_code:"920344",status:"running"},
  {session_id:"new",stock_code:"920344",status:"completed"},
  {session_id:"old",stock_code:"920344",status:"completed"},
];
test("返回时优先恢复该股运行任务，排除其他股票", () => {
  assert.deepEqual(selectDebateView(records,"920344",null,null,false),{sessionId:"running",historical:false});
});
test("新分析或失败后不把旧结论冒充本次结果，用户仍可主动查看历史", () => {
  assert.deepEqual(selectDebateView(records,"920344",null,null,true),{sessionId:null,historical:false});
  assert.deepEqual(selectDebateView(records,"920344",null,"current",true),{sessionId:"current",historical:false});
  assert.deepEqual(selectDebateView(records,"920344","old",null,true),{sessionId:"old",historical:true});
  assert.deepEqual(selectDebateView(records,"920344","other",null,true),{sessionId:null,historical:false});
});

test("已完成任务恢复结果，失败任务不冒充旧结论，排队任务也可恢复", () => {
  const completed = records.filter(record => record.status === "completed");
  assert.deepEqual(selectDebateView(completed,"920344",null,null,false),{sessionId:"new",historical:true});
  const failed = [{session_id:"failed",stock_code:"920344",status:"failed"}, ...completed];
  assert.deepEqual(selectDebateView(failed,"920344",null,null,false),{sessionId:"failed",historical:false});
  assert.deepEqual(selectDebateView([{session_id:"queued",stock_code:"920344",status:"queued"}],"920344",null,null,false),{sessionId:"queued",historical:false});
  assert.deepEqual(selectDebateView(records,"920344","old",null,false),{sessionId:"old",historical:true});
});
