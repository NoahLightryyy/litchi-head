import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { analysisFailureMessage, isBalanceFailure } from "../lib/debate-failure.ts";
import type { AgentAnalysis, DebateResult } from "../lib/types/debate.ts";

let current: DebateResult;
let triggerCount=0;
const mockHooks={
 useRunDebate:()=>({trigger:()=>{triggerCount++;},sessionId:null,running:false}),
 useDebateResult:()=>({data:current,isError:false,isTimedOut:false}),
 useDebateHistory:()=>({data:[{session_id:"old-failed",stock_code:"588110",instrument_type:"etf",status:"completed",created_at:"2026-11-04T15:00:00Z"}],isPending:false,refetch:()=>{}}),
};
function loadComponent(name:string): Record<string,ComponentType<Record<string,unknown>>> {
 const url=new URL(`../components/stock/${name}.tsx`,import.meta.url);
 const mod={exports:{}};
 const require=createRequire(url);
 new Function("require","module","exports",ts.transpileModule(readFileSync(url,"utf8"),{
  compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
 }).outputText)((path:string)=>{
   if(path==="@/lib/hooks/use-debate")return mockHooks;
   if(path==="./entry-plan-panel")return {EntryPlanPanel:()=>createElement("p",null,"入场计划测试入口")};
   if(path==="./horizon-research")return {HorizonResearch:()=>createElement("p",null,"三周期研究测试入口")};
   if(path==="./technical-supplement-panel")return {TechnicalSupplementPanel:()=>null};
   if(path.startsWith("./"))return loadComponent(path.slice(2));
   if(path.startsWith("@/lib/"))return require(`../../lib/${path.slice(6)}.ts`);
   return require(path);
 },mod,mod.exports);
 return mod.exports;
}
const panel=loadComponent("debate-panel").DebatePanel;
function failed(i:number):AgentAnalysis{return {agent_name:`master.${i}`,skill_name:`流派${i}`,skill_id:String(i),rating:"",score:0,confidence:0,direction:"Neutral",summary:"",analysis:"",success:false,latency_ms:0,error:"LLM 结构化输出解析失败: Error code: 402 - Insufficient Balance secret-provider"};}
const render=(analyses:AgentAnalysis[])=>{
 current={session_id:"old-failed",stock_code:"588110",stock_name:"测试ETF",instrument_type:"etf",analyses,vote_summary:{},evidence_limitations:[],review_report:null} as unknown as DebateResult;
 return renderToStaticMarkup(createElement(panel,{stockCode:"588110",stockName:"测试ETF",instrumentType:"etf"}));
};

test("old completed-but-failed session shows billing cause, no consensus or plan, no inference",()=>{
 const analyses=Array.from({length:5},(_,i)=>failed(i));
 const original=JSON.stringify(analyses); const html=render(analyses);
 assert.match(html,/本次 AI 分析未生成成功/);assert.match(html,/余额不足/);
 assert.match(html,/不会自动重跑付费分析/);assert.match(html,/未生成成功/);
 assert.doesNotMatch(html,/三周期研究测试入口|入场计划测试入口|条件或证据未齐|独立评审|secret-provider|0%/);
 assert.equal(triggerCount,0);assert.equal(JSON.stringify(analyses),original);
});

test("partial success retains genuine research and reports remaining failure",()=>{
 const analyses=Array.from({length:5},(_,i)=>failed(i));
 analyses[0]={...analyses[0],success:true,error:null,analysis:"真实论证",summary:"真实摘要"};
 const html=render(analyses);
 assert.match(html,/三周期研究测试入口/);assert.match(html,/入场计划测试入口/);
 assert.match(html,/4 位分析未成功/);assert.match(html,/余额不足/);assert.match(html,/真实论证/);
 assert.doesNotMatch(html,/本次 AI 分析未生成成功|secret-provider/);
});

test("unknown or empty results do not invent billing failures or opinions",()=>{
 for(const analyses of [[],[{...failed(0),error:"<script>secret</script>"}]]){
  const html=render(analyses);
  assert.match(html,/未生成研究结论/);
  assert.doesNotMatch(html,/余额不足|三周期研究测试入口|入场计划测试入口|<script>|secret/);
 }
 for(const value of [null,undefined,"HTTP 402","条件不足"]){assert.equal(isBalanceFailure(value),false);}
 assert.equal(analysisFailureMessage("LLM 结构化输出解析失败: Error code: 401 - secret"),"模型服务请求失败");
 assert.equal(analysisFailureMessage("2 validation errors"),"模型返回内容未通过校验");
});
