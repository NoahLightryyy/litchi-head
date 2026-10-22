import test from "node:test";
import assert from "node:assert/strict";
import {parseEtfDetail} from "../lib/etf-display.ts";
import {parseDiscoveryResults,discoveryHref} from "../lib/discovery-search.ts";

const fixture = () => ({schema_version:1,identity:{code:"510050",symbol:"sh510050",exchange:"SH",name:"上证50ETF",instrument_type:"etf"},
  quote:{price:2.919,previous_close:2.918,change:2.919-2.918,change_pct:(2.919/2.918-1)*100,open:null,high:2.93,low:2.88,quoted_at:"2026-10-09T15:34:59+08:00",source_name:"50ETF"},
  status:"ready",source:"sina",source_url:"https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf",catalog_fetched_at:"2026-10-09T16:00:00+08:00",fetched_at:"2026-10-09T16:00:00+08:00",limitations:["单源"]});

test("ETF独立详情保留三位价格及完整源日期，缺值不补零",()=>{
  const data=parseEtfDetail(fixture(),"510050");
  assert.equal(data.quote?.price,2.919);
  assert.equal(data.quote?.open,null);
  assert.equal(data.quote?.quoted_at,"2026-10-09T15:34:59+08:00");
  assert.equal(parseEtfDetail({...fixture(),status:"partial",quote:null},"510050").quote,null);
});
test("ETF拒绝错身份、错市场、不明类型、不安全来源、未来日期及无效行情",()=>{
  for (const update of [
    {identity:{...fixture().identity,code:"159915"}},
    {identity:{...fixture().identity,exchange:"SZ"}},
    {identity:{...fixture().identity,instrument_type:"stock"}},
    {source_url:"javascript:alert(1)"},
    {quote:{...fixture().quote,quoted_at:"2099-10-09T15:34:59+08:00"}},
    {quote:{...fixture().quote,price:NaN}},
    {quote:{...fixture().quote,change:100}},
    {quote:null},
  ]) assert.throws(()=>parseEtfDetail({...fixture(),...update},"510050"));
});
test("搜索ETF跳独立页面，个股与板块入口保持对应类型",()=>{
  const result=parseDiscoveryResults({data:[{code:"159915",name:"创业板",kind:"etf"}],total:1,failed_sources:["股票目录"]});
  assert.equal(discoveryHref(result.data[0]),"/etf/159915");
  assert.equal(discoveryHref({code:"688012",name:"中微",kind:"stock"}),"/stock/688012");
  assert.equal(discoveryHref({code:"BK1326",name:"半导体设备",kind:"industry"}),"/sector/BK1326");
  assert.throws(()=>parseDiscoveryResults({data:[{code:"../stock/600000",name:"假身份",kind:"etf"}],total:1,failed_sources:[]}));
});
