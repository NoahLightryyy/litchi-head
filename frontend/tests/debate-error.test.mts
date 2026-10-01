import test from "node:test";
import assert from "node:assert/strict";
import { debateErrorMessage } from "../lib/debate-error.ts";

test("证据门禁不冒充后端断线，且不暴露原始错误", () => {
  assert.match(debateErrorMessage({code:"EVIDENCE_INCOMPLETE", detail:{capability:"stock_identity"}}), /基础信息/);
  assert.match(debateErrorMessage({code:"EVIDENCE_INCOMPLETE"}), /市场证据/);
  assert.match(debateErrorMessage({code:"NETWORK_ERROR"}), /无法连接/);
  assert.match(debateErrorMessage({status:429}), /频繁/);
  assert.match(debateErrorMessage({code:"ANALYSIS_NOT_CONFIGURED"}), /DeepSeek.*尚未配置/);
  assert.doesNotMatch(debateErrorMessage({code:"ANALYSIS_NOT_CONFIGURED"}), /稍后重试/);
  assert.doesNotMatch(debateErrorMessage({message:"secret upstream URL"}), /secret/);
});
