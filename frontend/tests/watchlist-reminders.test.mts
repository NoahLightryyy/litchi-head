import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as quoteDisplay from "../lib/quote-display.ts";
import * as reminders from "../lib/watchlist-reminders.ts";
import type { EntryPlanResult } from "../lib/entry-plan.ts";
import type { StockQuote } from "../lib/types/stock.ts";

const quote: StockQuote = {code:"688648",name:"中邮科技",price:34.66,change:5.78,change_pct:20.01,open:30.5,high:34.66,low:30.43,prev_close:28.88,volume:100,turnover_rate:null,fund_flow:null,market_cap:null,amount:100,source:"sina",fetched_at:"2026-10-26T15:00:00+08:00"};
const entry={code:quote.code,name:quote.name,note:"原来的备注",updatedAt:"2026-10-26T08:00:00Z"};
const record={session_id:"saved",stock_code:quote.code,instrument_type:"stock",status:"completed",created_at:"2026-10-26T08:00:00Z"};
function plan(): EntryPlanResult {
  return {generated_at:"2026-10-26T08:00:00Z",plans:["short","medium","long"].map(horizon=>({horizon,status:"waiting",summary:"等价格站稳",conditions:[{condition:"站稳再看",status:"unmet"}],invalidation:["经营出现变化"]}))} as EntryPlanResult;
}

test("不用写备注就能加入；重复加入不清空旧备注或更新时间",()=>{
  const next=reminders.addWatchEntry([], {code:quote.code,name:quote.name}, entry.updatedAt);
  assert.equal(next[0].note, "");
  const existing=[entry]; assert.equal(reminders.addWatchEntry(existing, entry, "later"), existing);
  assert.equal(existing[0].note,"原来的备注");
});
test("报价拒绝错股、非数值与错误时间，涨跌只给观察提醒",()=>{
  assert.equal(reminders.checkedWatchQuote(null,quote.code),null);
  for(const patch of [{code:"600000"},{price:0},{change_pct:NaN},{fetched_at:"invalid"}]) assert.throws(()=>reminders.checkedWatchQuote({...quote,...patch},quote.code));
  assert.match(reminders.priceReminder(quote).detail,/不等于现在买/);
  assert.match(reminders.priceReminder({...quote,change_pct:-1}).detail,/跌了不等于便宜/);
  assert.match(reminders.priceReminder({...quote,change_pct:0}).title,/持平/);
});
test("按真实日期选最新已完成股票分析，基金和别的股票不能混入",()=>{
  const value=reminders.latestWatchResearch([record,{...record,session_id:"fund",instrument_type:"etf",created_at:"2026-10-27T08:00:00Z"},{...record,session_id:"new",status:"running",created_at:"2026-10-27T08:00:00Z"}],quote.code);
  assert.equal(value.completed?.session_id,"saved"); assert.equal(value.latestStatus,"running");
  assert.equal(reminders.latestWatchResearch([{...record,stock_code:"600000"}],quote.code).completed,null);
  assert.throws(()=>reminders.latestWatchResearch([{...record,created_at:"invalid"}],quote.code));
});
test("读取自选只使用已有GET，不会新建AI分析；没有记录不继续请求",async()=>{
  const prior=globalThis.fetch; const requests:{url:string;method:string}[]=[];
  let hasHistory=true;
  globalThis.fetch=async(url, init)=>{requests.push({url:String(url),method:init?.method??"GET"});return new Response(JSON.stringify(String(url).includes("/history")?{data:hasHistory?[record]:[]}:null),{status:200});};
  try {
    assert.equal((await reminders.readWatchResearch(quote.code,new AbortController().signal)).plan,null);
    assert.equal(requests.length,2); assert.ok(requests.every(r=>r.method==="GET"));
    assert.match(requests[1].url,/saved\/entry-plan/);
    hasHistory=false; requests.length=0; await reminders.readWatchResearch(quote.code,new AbortController().signal); assert.equal(requests.length,1);
  }finally{globalThis.fetch=prior;}
});
function compile(path:string, overrides:Record<string,unknown>={}) {
  const url=new URL(path,import.meta.url), mod={exports:{} as Record<string,unknown>}, require=createRequire(url);
  new Function("require","module","exports",ts.transpileModule(readFileSync(url,"utf8"),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(
    (name:string)=>name in overrides?overrides[name]: name==="@/lib/quote-display"?quoteDisplay:name==="@/lib/watchlist-reminders"?reminders:name==="@/lib/api/client"?{}:name==="next/link"?{default:(p:{href:string;children:unknown})=>createElement("a",{href:p.href},p.children as never)}:require(name),mod,mod.exports);
  return mod.exports;
}
interface ContentProps {code:string;quote?:StockQuote|null;research?:reminders.WatchResearch;quoteLoading:boolean;researchLoading:boolean;quoteError:boolean;researchError:boolean;offline:boolean;onRefresh:()=>void}
const Content=compile("../components/stock/watch-reminders.tsx").WatchReminderContent as ComponentType<ContentProps>;
const render=(extra:Partial<ContentProps>={})=>renderToStaticMarkup(createElement(Content,{code:quote.code,quoteLoading:false,researchLoading:false,quoteError:false,researchError:false,offline:false,onRefresh:()=>{},...extra}));
test("普通人先看提醒，旧分析时间不冒充新信号，细节折叠且详情可跳转",()=>{
  const html=render({quote,research:{latestStatus:"completed",plan:plan()}});
  assert.match(html,/买入条件还没凑齐/); assert.match(html,/2026\/10\/26/);
  assert.match(html,/不能当成刚刚出现的信号/);assert.match(html,/href="\/stock\/688648#research"/);
  assert.doesNotMatch(html,/<details[^>]*\sopen/);
  assert.equal((html.match(/具体等什么、什么情况要小心/g)??[]).length,3);
  const old=plan();old.plans[0].status="consider";assert.match(render({research:{plan:old,latestStatus:"completed"}}),/出现过值得留意的买入信号/);
});
test("失败和离线保留已有价格、提醒；缺数据不称没有风险",()=>{
  const html=render({quote,research:{plan:plan(),latestStatus:"failed"},quoteError:true,researchError:true,offline:true});
  assert.match(html,/网络断了/);assert.match(html,/34.66/);assert.match(html,/保留的是之前的价格/);assert.match(html,/买入条件还没凑齐/);
  assert.match(render({researchError:true}),/不代表没有风险/); assert.match(render({quoteLoading:true}),/正在查看价格变化/);
});
test("自选首屏只要求搜索股票，旧备注保留，每页只挂载十只提醒",()=>{
  const entries=Array.from({length:12},(_,i)=>({...entry,code:String(600000+i)}));
  let mounted=0;
  const Page=compile("../app/watchlist/page.tsx",{
    "@/lib/hooks/use-research-list":{useResearchList:()=>({entries,error:null,readError:null,save:()=>true})},
    "@/lib/hooks/use-debounce":{useDebounce:(v:string)=>v},
    "@tanstack/react-query":{useQuery:()=>({})},
    "@/components/stock/watch-reminders":{WatchReminders:()=>{mounted++;return createElement("span",null,"自动提醒");}},
  }).default as ComponentType;
  const html=renderToStaticMarkup(createElement(Page));
  assert.equal(mounted,10);assert.match(html,/每页 10 只/);assert.match(html,/原来的备注/);
  assert.doesNotMatch(html,/跟踪假设与验证条件|下次财报中核对/);assert.match(html,/搜名称或代码就行/);
});


test("自选报价也显示已接入的腾讯来源名称", () => {
  assert.match(render({quote: {...quote, source: "tencent"}}), /腾讯/);
});
