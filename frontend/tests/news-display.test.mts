import assert from "node:assert/strict";
import test from "node:test";
import {newsPage, parseNewsDisplay, publicationLabel, type NewsDisplay} from "../lib/news-display.ts";

const fixture = (): NewsDisplay => ({schema_version:1, symbol:"300199", company_name:"翰宇药业", status:"ready",
  start_date:"2026-09-02", end_date:"2026-10-01", fetched_at:"2026-10-01T12:00:00+08:00", cached:false,
  purpose:"display_only", sources:[
    {source:"eastmoney", status:"success", matched:1, scanned:1, total_candidates:1, error_code:null},
    {source:"cninfo", status:"empty", matched:0, scanned:0, total_candidates:0, error_code:null}],
  items:[{id:"abc",title:"翰宇药业消息",kind:"report",published_at:"2026-09-30T14:05:00+08:00",time_precision:"second",
    association:"title_match",provenance:[{source:"eastmoney",publisher:"媒体",url:"https://finance.eastmoney.com/a/1.html"}]}]});

test("接受真实时间与来源，失败不能冒充空结果",()=> {
  assert.equal(parseNewsDisplay(fixture(),"300199").items.length,1);
  const v=fixture();v.status="failed";
  assert.throws(()=>parseNewsDisplay(v,"300199"));
  v.items=[];assert.equal(parseNewsDisplay(v,"300199").status,"failed");
});
test("拒绝错股、重复、危险链接、错误时间和类型",()=> {
  assert.throws(()=>parseNewsDisplay(fixture(),"000001"));
  for(const mutate of [
    (v:NewsDisplay)=>{v.items.push(v.items[0]);},
    (v:NewsDisplay)=>{v.items[0].provenance[0].url="javascript:alert(1)";},
    (v:NewsDisplay)=>{v.items[0].published_at="2026-09-30 14:05:00";},
    (v:NewsDisplay)=>{v.items[0].published_at="2027-09-30T14:05:00+08:00";},
    (v:NewsDisplay)=>{v.items[0].kind="announcement";},
    (v:NewsDisplay)=>{v.items[0].title="nan";},
  ]) {const v=fixture();mutate(v);assert.throws(()=>parseNewsDisplay(v,"300199"));}
});
test("公告保留日期精度，未知发布时间不补成抓取时间",()=>{
  const v=fixture();const item=v.items[0];
  item.kind="announcement";item.association="official_code";item.time_precision="date";item.published_at="2026-09-30";
  assert.equal(publicationLabel(parseNewsDisplay(v,"300199").items[0]),"2026-09-30（公告日期）");
  v.fetched_at="2026-10-01T00:30:00+08:00";item.published_at="2026-10-01";
  assert.doesNotThrow(()=>parseNewsDisplay(v,"300199"));
  item.published_at="2026-10-02";assert.throws(()=>parseNewsDisplay(v,"300199"));
  item.time_precision="unknown";item.published_at=null;
  assert.equal(publicationLabel(item),"发布时间未提供");
});
test("分类搜索分页不漏尾页，筛选后页码夹紧",()=>{
  const items=Array.from({length:23},(_,i)=>({...fixture().items[0],id:String(i),title:`新闻 ${i}`,kind:i<3?"announcement" as const:"report" as const}));
  assert.equal(newsPage(items,"all","",3).items.length,3);
  const a=newsPage(items,"announcement","",3);assert.equal(a.current,1);assert.equal(a.total,3);
  assert.equal(newsPage(items,"report","新闻 22",1).items[0].id,"22");
  assert.equal(newsPage(items,"all","不存在",1).items.length,0);
});
