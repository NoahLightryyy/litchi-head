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
