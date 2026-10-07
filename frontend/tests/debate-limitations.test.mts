import test from "node:test";
import assert from "node:assert/strict";
import { debateLimitations } from "../lib/debate-limitations.ts";

test("有限证据与评审缺失不会被成功响应掩盖", () => {
  const notes = debateLimitations({ evidence_limitations: [{capability:"news"}],
    review_report:null, analyses:[{success:true},{success:false}] });
  assert.match(notes.join(" "), /关联新闻.*证据不完整/);
  assert.match(notes.join(" "), /未进入交易决策/);
  assert.match(notes.join(" "), /未取得有效独立评审/);
  assert.match(notes.join(" "), /1 位分析未成功/);
  assert.deepEqual(debateLimitations(undefined), []);
  assert.deepEqual(debateLimitations({review_report:{overall_quality:0.8}, analyses:[{success:true}]}), []);
});

test("休市研究展示真实覆盖说明，保留交易限制且兼容旧结果", () => {
  const notes = debateLimitations({evidence_limitations: [
    {capability:"realtime_quote", research_note:"休市研究：09/30 收盘报价，新浪单源，未交叉验证。"},
    {capability:"news", research_note:"新浪新闻覆盖 10/05 至 10/06，匹配 0 条，未覆盖完整近 3 天。"},
  ]});
  assert.match(notes.join(" "), /休市研究.*单源/);
  assert.match(notes.join(" "), /未覆盖完整近 3 天/);
  assert.match(notes.join(" "), /未进入交易决策/);
  assert.ok(!notes.some(note => note.includes("个股报价、关联新闻证据不完整")));
  assert.match(debateLimitations({evidence_limitations:[
    {capability:"news",research_note:" "},
  ]}).join(" "), /关联新闻证据不完整/);
});
