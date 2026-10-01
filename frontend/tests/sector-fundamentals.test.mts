import test from "node:test";
import assert from "node:assert/strict";
import { checkedResearch, displayMetric, publicationDate, FUNDAMENTAL_ROWS, type Research } from "../lib/sector-fundamentals.ts";
function sample(): Research {
  return {schema_version:1, stock_code:"300199",status:"partial",report_date:"2026-06-30",fetched_at:"2026-10-01T00:00:00Z",source:"sina_consolidated_statements",verification:"single_source",retryable:false,warnings:[],
    statements:[{kind:"lrb",report_date:"2026-06-30",published_at:"2026-08-21",scope:"合并期末",currency:"CNY",source_url:"https://quotes.sina.cn/report",amounts:{}}],
    metrics:Object.fromEntries(FUNDAMENTAL_ROWS.map(({key}) => [key,{value:null,unit:"%",basis:"formula",reason:"missing"}]))};
}
test("reject incompatible contracts, identity, dates, numbers and source URLs", () => {
  assert.equal(checkedResearch(sample(),"300199").report_date,"2026-06-30");
  for (const change of [{schema_version:2},{stock_code:"600276"},{report_date:"2026-02-30"}]) assert.throws(()=>checkedResearch({...sample(),...change},"300199"));
  const bad=sample(); bad.metrics.gross_margin!.value=NaN;
  assert.throws(()=>checkedResearch(bad,"300199"));
  bad.metrics.gross_margin!.value=0;bad.statements[0].source_url="javascript:alert(1)";
  assert.throws(()=>checkedResearch(bad,"300199"));
});
test("distinguish real zero, negative, missing and currency units", () => {
  const metric={value:0,unit:"%",basis:"formula",reason:null};
  assert.equal(displayMetric(metric),"0.00%");
  assert.equal(displayMetric({...metric,value:-1.5}),"-1.50%");
  assert.equal(displayMetric({...metric,value:688286621.3,unit:"元"}),"6.88亿");
  assert.equal(displayMetric({...metric,value:null,reason:"missing"}),"—");
});
test("publication is never substituted by retrieval time; preserve stale status", () => {
  const data=sample();
  assert.equal(publicationDate(data),"2026-08-21");
  data.statements[0].published_at=null;
  assert.equal(publicationDate(data),"未提供");
  data.status="stale";
  assert.equal(checkedResearch(data,"300199").status,"stale");
});
