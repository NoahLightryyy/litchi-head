import test from "node:test";
import assert from "node:assert/strict";
import { parseResearchList } from "../lib/research-list.ts";
import { parseHoldings, portfolioSummary } from "../lib/portfolio.ts";
const holding = {id:"one",kind:"stock",code:"000001",name:"测试资产",account:"测试",sector:"",value:200,cost:null,asOf:"2026-09-09"};
test("本机记录缺失为空，损坏拒绝而非覆盖",()=>{
 assert.deepEqual(parseResearchList(null),[]); assert.deepEqual(parseHoldings(null),[]);
 for(const raw of ["bad","{}",JSON.stringify([{...holding,value:-1}]),JSON.stringify([{...holding,asOf:"2026-02-30"}]),JSON.stringify([holding,holding])]) assert.throws(()=>parseHoldings(raw));
 assert.throws(()=>parseResearchList(JSON.stringify([{code:"../../x",name:"x",note:"",updatedAt:"2026-09-09"}])));
});
test("持仓汇总保持未知成本与零分母，不推测基金穿透",()=>{
 const entries=parseHoldings(JSON.stringify([holding,{...holding,id:"two",kind:"fund",value:300,sector:"科技",cost:250}]));
 const summary=portfolioSummary(entries); assert.equal(summary.total,500); assert.equal(summary.costComplete,false); assert.equal(summary.largestWeight,0.6); assert.deepEqual(summary.groups,[["科技",300],["未分类",200]]);
 assert.equal(portfolioSummary([]).largestWeight,null); assert.equal(portfolioSummary([{...entries[0],value:0}]).largestWeight,null);
});
test("自选重复代码拒绝，保留用户假设",()=>{
 const item={code:"000001",name:"测试",note:"待验证",updatedAt:"2026-09-09T00:00:00Z"};
 assert.deepEqual(parseResearchList(JSON.stringify([item])),[item]); assert.throws(()=>parseResearchList(JSON.stringify([item,item])));
});


test("恢复前先校验全部数据，第二项写失败则还原两份原记录",async()=>{
 const {restorePersonalRecords}=await import("../lib/personal-backup.ts");
 const values=new Map([["litchi.research-list.v1","old-watch"],["litchi.holdings.v1","old-hold"]]);
 let writes=0;
 const store={getItem:(key:string)=>values.get(key)??null,removeItem:(key:string)=>{values.delete(key);},setItem:(key:string,value:string)=>{writes++;if(writes===2)throw new Error("quota");values.set(key,value);}};
 assert.throws(()=>restorePersonalRecords(store,{watchlist:[],holdings:[{...holding,value:-1}]})); assert.equal(writes,0);
 assert.throws(()=>restorePersonalRecords(store,{watchlist:[],holdings:[holding]}),/已保留原记录/);
 assert.equal(values.get("litchi.research-list.v1"),"old-watch"); assert.equal(values.get("litchi.holdings.v1"),"old-hold");
});
