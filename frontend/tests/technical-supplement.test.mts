import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as lib from "../lib/technical-supplement.ts";

function fixture(): lib.TechnicalSupplement {
  return {stock_code:"002885",status:"available",fetched_at:"2026-11-04T12:00:00Z",sources:["tencent"],
    diagnostics:{tencent:"success_data"},methodology:"完整序列预热",adjusted:{status:"available",
      price_basis:"provider_qfq_current",source:"tencent",fetched_at:"2026-11-04T12:00:00Z",
      data_start:"2026-06-01",data_end:"2026-11-03",bar_count:100,reason:null,methodology:"来源当前复权，非官方审计",
      indicators:[{trade_date:"2026-11-03",ma:{ma5:20,ma20:22,ma60:null},rsi14:30,macd:{histogram:-0.2},kdj:{j:15}}]},
    volume:{status:"available",data_date:"2026-11-03",sample_bars:100,volume_basis:"raw_shares",
      latest_shares:500000,previous5_mean_shares:1000000,previous20_mean_shares:2000000,
      ratio_to_previous5:0.5,ratio_to_previous20:0.25,comparison:"below_both",methodology:"不含当日，非盘中量比"}};
}
const url=new URL("../components/stock/technical-supplement-view.tsx",import.meta.url);
const mod={exports:{} as {TechnicalSupplementView:ComponentType<{data:lib.TechnicalSupplement}>}};
new Function("require","module","exports",ts.transpileModule(readFileSync(url,"utf8"),{
  compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
}).outputText)((name:string)=>name==="@/lib/technical-supplement"?lib:createRequire(url)(name),mod,mod.exports);
const render=(data:lib.TechnicalSupplement)=>renderToStaticMarkup(createElement(mod.exports.TechnicalSupplementView,{data}));

test("valid one-source facts separate data availability from an unmet volume condition",()=>{
  const data=lib.parseTechnicalSupplement(fixture(),"002885"); const html=render(data);
  assert.match(html,/前复权数据已补齐/); assert.match(html,/成交量数据已补齐/);
  assert.match(html,/50.00 万股/); assert.match(html,/0.50 倍（-50.0%）/);
  assert.match(html,/放量条件还没出现/); assert.match(html,/不会自动改写下方历史研究的结论/);
  assert.doesNotMatch(html,/<details[^>]* open/);
  assert.match(html,/2026-11-03/); assert.match(html,/MA60<\/dt><dd>—/);
});
test("available volume is displayed independently when QFQ fails",()=>{
  const data=fixture(); data.adjusted={...data.adjusted,status:"unavailable",indicators:[],bar_count:0,data_start:null,data_end:null,reason:"请求失败"};
  const html=render(lib.parseTechnicalSupplement(data,"002885"));
  assert.match(html,/前复权数据暂未补齐/); assert.match(html,/成交量数据已补齐/);
  assert.doesNotMatch(html,/前复权数据已补齐/);
});
test("empty history and short or zero windows do not invent ratios",()=>{
  const data=fixture(); data.status="unavailable"; data.adjusted={...data.adjusted,status:"unavailable",indicators:[],bar_count:0,data_start:null,data_end:null};
  data.volume={...data.volume,status:"unavailable",data_date:null,sample_bars:0,latest_shares:null,previous5_mean_shares:null,previous20_mean_shares:null,ratio_to_previous5:null,ratio_to_previous20:null,comparison:"insufficient"};
  assert.match(render(lib.parseTechnicalSupplement(data,"002885")),/成交量暂未取得/);
  data.status="available"; data.volume={...data.volume,status:"partial",data_date:"2026-11-03",sample_bars:5,latest_shares:0};
  const html=render(lib.parseTechnicalSupplement(data,"002885")); assert.match(html,/暂不能计算/); assert.doesNotMatch(html,/0.00 倍/);
});
for(const mutate of [
  (x:lib.TechnicalSupplement)=>{x.stock_code="000001";},
  (x:lib.TechnicalSupplement)=>{x.adjusted.price_basis="raw" as never;},
  (x:lib.TechnicalSupplement)=>{x.volume.ratio_to_previous5=NaN;},
  (x:lib.TechnicalSupplement)=>{x.volume.latest_shares=-1;},
  (x:lib.TechnicalSupplement)=>{x.volume.data_date="2026-11-02";},
  (x:lib.TechnicalSupplement)=>{x.adjusted.indicators[0].rsi14=Infinity;},
  (x:lib.TechnicalSupplement)=>{x.volume.sample_bars=3;},
]) test("foreign, invalid basis/number/date/coverage is rejected",()=>{
  const x=fixture(); mutate(x); assert.throws(()=>lib.parseTechnicalSupplement(x,"002885"));
});
test("higher volume does not promise a reversal, mixed/equal/insufficient are explicit",()=>{
  const x=fixture(); x.volume.comparison="above_both";
  assert.match(lib.volumeComparisonText(x.volume),/不能确认上涨或反转/);
  for(const comparison of ["equal_both","mixed","insufficient"] as const){
    x.volume.comparison=comparison; assert.ok(lib.volumeComparisonText(x.volume));
  }
});
test("upstream prose is escaped, source details remain collapsed",()=>{
  const x=fixture(); x.adjusted.methodology="<script>evil()</script>";
  const html=render(x); assert.match(html,/&lt;script&gt;/); assert.doesNotMatch(html,/<script>/);
});


let queryState: Record<string, unknown> = {};
const panelUrl = new URL("../components/stock/technical-supplement-panel.tsx", import.meta.url);
const panel = { exports: {} as { TechnicalSupplementPanel: ComponentType<{stockCode:string}> } };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(panelUrl,"utf8"), {
  compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText)((name:string) => name === "@/lib/hooks/use-technical-supplement"
  ? {useTechnicalSupplement: () => queryState}
  : name === "./technical-supplement-view" ? mod.exports : createRequire(panelUrl)(name), panel, panel.exports);
const renderPanel = () => renderToStaticMarkup(createElement(panel.exports.TechnicalSupplementPanel,{stockCode:"002885"}));
test("panel loading, retryable error and stale cached-data error are separate", () => {
  queryState={isPending:true,isFetching:true};
  assert.match(renderPanel(),/正在读取前复权日线和成交量/);
  assert.match(renderPanel(),/disabled/);
  queryState={isError:true};
  assert.match(renderPanel(),/可稍后重新读取/);
  assert.doesNotMatch(renderPanel(),/前复权数据已补齐/);
  queryState={isError:true,data:fixture()};
  assert.match(renderPanel(),/保留上次资料/);
  assert.match(renderPanel(),/2026-11-03/);
  queryState={data:{...fixture(),stock_code:"000001"}};
  assert.doesNotMatch(renderPanel(),/前复权数据已补齐/);
});
