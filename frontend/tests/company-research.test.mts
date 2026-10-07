import test from "node:test";
import assert from "node:assert/strict";
import { parseCompanyResearch, type CompanyResearch } from "../lib/company-research.ts";

function fixture(): CompanyResearch {
  const insight = () => ({ text: "主营业务对应生产环节", basis: "inference" as const, source_ids: ["profile"] });
  return {
    schema_version: 1, stock_code: "920344", company_name: "测试药业", model: "test",
    generated_at: "2026-10-06T10:00:00Z", fetched_at: "2026-10-06T09:59:00Z",
    review_status: "ai_unreviewed", purpose: "company_context_only", gaps: ["只读取节选"],
    sources: [{ id: "profile", title: "公司资料", url: "https://vip.stock.finance.sina.com.cn/test",
      published_at: null, excerpt: "研究、生产和销售" }],
    interpretation: { niche: insight(), upstream: insight(), role: insight(), downstream: insight(),
      highlights: [insight()], watchpoints: [insight()] },
  };
}

test("empty is distinct from saved evidence-backed interpretation", () => {
  assert.equal(parseCompanyResearch(null, "920344"), null);
  const value = fixture();
  assert.deepEqual(parseCompanyResearch(value, "920344"), value);
});

test("rejects another stock's result on navigation", () => {
  assert.throws(() => parseCompanyResearch(fixture(), "600519"));
});

test("rejects invented, duplicate and missing citations", () => {
  for (const ids of [["invented"], ["profile", "profile"], []]) {
    const value = fixture(); value.interpretation.niche.source_ids = ids;
    assert.throws(() => parseCompanyResearch(value, "920344"));
  }
});

test("rejects unsafe links and unrecognized publishers", () => {
  for (const url of ["javascript:alert(1)", "https://evil.test/", "https://user@vip.stock.finance.sina.com.cn/"]) {
    const value = fixture(); value.sources[0].url = url;
    assert.throws(() => parseCompanyResearch(value, "920344"));
  }
});

test("rejects missing watchpoints, identity and timezone", () => {
  const edits = [
    (v: CompanyResearch) => { v.interpretation.watchpoints = []; },
    (v: CompanyResearch) => { v.generated_at = "2026-10-06T10:00:00"; },
    (v: CompanyResearch) => { v.company_name = ""; },
    (v: CompanyResearch) => { v.sources.push(v.sources[0]); },
  ];
  for (const edit of edits) {
    const value = fixture(); edit(value);
    assert.throws(() => parseCompanyResearch(value, "920344"));
  }
});

test("competition is backward compatible and must carry valid citations", () => {
  const value = fixture();
  assert.ok(parseCompanyResearch(value, "920344"));
  value.interpretation.competition = [{ text: "优势依赖研发投入", basis: "inference", source_ids: ["profile"] }];
  assert.ok(parseCompanyResearch(value, "920344"));
  value.interpretation.competition[0].source_ids = ["invented"];
  assert.throws(() => parseCompanyResearch(value, "920344"));
});

test("stock impact retains legacy compatibility and requires mechanism, horizon and conditions", () => {
  const value = fixture();
  value.interpretation.highlights[0].stock_impact = {mechanism:"成本影响盈利",horizon:"中期1至3个月",conditions:"毛利率改善才成立"};
  assert.ok(parseCompanyResearch(value,"920344"));
  value.interpretation.highlights[0].stock_impact.horizon = "";
  assert.throws(()=>parseCompanyResearch(value,"920344"));
});
