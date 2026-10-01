import test from "node:test";
import assert from "node:assert/strict";
import {buildAction,parseActionList,parseActionWrite,restoreAttempt,type ActionDraft} from "../lib/user-action-ledger.ts";
const draft:ActionDraft={stock_code:"300199",session_id:"manual-test",action:"buy",local_time:"2026-10-01T10:30",offset:"+08:00",quantity:"",execution_price:"",currency:"",stated_reason:"自己填写的理由"};
const payload=buildAction(draft,"test-id");
const event={...payload,schema_version:"1",event_id:"ua_test",user_id:"test-owner",recorded_at:"2026-10-01T03:00:00Z",source:"user_reported",ai_snapshot_status:"unverified",limitations:["ai_snapshot_not_verified","user_identity_not_authenticated"]};
const envelope={data:event,meta:{status:"recorded",immutable:true,retry_mode:"idempotent"}};
test("未知成交事实不补零，不推断币种或盈亏",()=>{
  assert.equal(payload.quantity,null);assert.equal(payload.execution_price,null);assert.equal(payload.currency,null);
  assert.equal(payload.occurred_at,"2026-10-01T10:30:00+08:00");
  assert.equal("return_pct" in payload,false);
});
test("时间必须是实际日期且用户显式选时区，零成交和单独币种拒绝",()=>{
  for(const patch of [{offset:""},{local_time:"2026-02-30T12:00"},{offset:"+14:30"},{action:"unknown"},{quantity:"0"},{quantity:"NaN"},{execution_price:"12"},{currency:"CNY"}]) assert.throws(()=>buildAction({...draft,...patch},"test-id"));
  const china=buildAction(draft,"id1"),paris=buildAction({...draft,local_time:"2026-10-01T04:30",offset:"+02:00"},"id2");
  assert.equal(Date.parse(china.occurred_at),Date.parse(paris.occurred_at));
});
test("响应校验归属、幂等键、事实、AI未核验状态与完整限制",()=>{
  assert.equal(parseActionWrite(envelope,"test-owner",payload).replayed,false);
  assert.equal(parseActionWrite({...envelope,meta:{...envelope.meta,status:"replayed"}},"test-owner",payload).replayed,true);
  for(const patch of [{user_id:"other"},{stock_code:"300913"},{quantity:"1"},{action:"sell"},{stated_reason:"changed"},{ai_snapshot_status:"linked"},{limitations:[]},{occurred_at:"2026-10-01T10:30:00"}]) assert.throws(()=>parseActionWrite({...envelope,data:{...event,...patch}},"test-owner",payload));
});
test("成交十进制不经浮点数，等值序列可接受但微小改变拒绝",()=>{
  const p=buildAction({...draft,quantity:"100.00",execution_price:"0.0000000001",currency:"CNY"},"id-money");
  const e={...event,...p,quantity:"1E+2",execution_price:"1E-10"};
  assert.equal(parseActionWrite({...envelope,data:e},"test-owner",p).event.currency,"CNY");
  assert.throws(()=>parseActionWrite({...envelope,data:{...e,execution_price:"1.00000000001E-10"}},"test-owner",p));
});
test("分页边界、重复记录和跨用户响应不得作为有效列表",()=>{
  const v={data:[event],meta:{total:1,offset:0,limit:10,immutable:true}};
  assert.equal(parseActionList(v,"test-owner",0,10).events.length,1);
  assert.throws(()=>parseActionList(v,"other",0,10));
  assert.throws(()=>parseActionList({...v,data:[event,event]},"test-owner",0,10));
  assert.throws(()=>parseActionList(v,"test-owner",10,10));
  assert.equal(parseActionList({...v,data:[],meta:{...v.meta,total:0}},"test-owner",0,10).total,0);
});
test("刷新后恢复原事实和幂等标识，损坏草稿不发出",()=>{
  const restored=restoreAttempt(JSON.stringify({owner:"test-owner",draft,clientId:"test-id"}));
  assert.deepEqual(restored.payload,payload);
  for(const raw of ["bad","{}",JSON.stringify({owner:"test-owner",draft:{...draft,quantity:0},clientId:"id"})]) assert.throws(()=>restoreAttempt(raw));
});
test("真实API客户端保留用户头、JSON类型与幂等回放信封",async()=>{
  const {saveAction}=await import("../lib/api/user-actions.ts");
  const original=globalThis.fetch;
  let calls=0;
  globalThis.fetch=async(_input,init)=>{
    calls++;const headers=new Headers(init?.headers);
    assert.equal(headers.get("X-User-Id"),"test-owner");assert.equal(headers.get("Content-Type"),"application/json");
    assert.deepEqual(JSON.parse(String(init?.body)),payload);
    return new Response(JSON.stringify({...envelope,meta:{...envelope.meta,status:"replayed"}}),{status:201});
  };
  try {assert.equal((await saveAction("test-owner",payload)).replayed,true);assert.equal(calls,1);}finally{globalThis.fetch=original;}
});
test("写入冲突不会自动换键或重试",async()=>{
  const {saveAction}=await import("../lib/api/user-actions.ts");const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async()=>{calls++;return new Response(JSON.stringify({error:{code:"USER_ACTION_IDEMPOTENCY_CONFLICT",message:"冲突",retryable:false}}),{status:409});};
  try{await assert.rejects(saveAction("test-owner",payload),{code:"USER_ACTION_IDEMPOTENCY_CONFLICT"});assert.equal(calls,1);}finally{globalThis.fetch=original;}
});
