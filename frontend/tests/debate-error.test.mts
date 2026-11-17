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


test("balance and total generation failure are not market data failures", () => {
 assert.match(debateErrorMessage({code:"ANALYSIS_BALANCE_INSUFFICIENT"}),/余额不足/);
 assert.doesNotMatch(debateErrorMessage({code:"ANALYSIS_BALANCE_INSUFFICIENT"}),/稍后重试|市场证据/);
 assert.match(debateErrorMessage({code:"ANALYSIS_FAILED"}),/未生成研究结论/);
});

test("断网、超时和余额不足各自写明原因，笼统失败不冒充断网", async () => {
  const { analysisFailureMessage, failureReasonSummary, isNetworkFailure, noResearchMessage } = await import("../lib/debate-failure.ts");
  const network = "LLM_NETWORK_UNAVAILABLE: 网络连接中断，未能连上模型服务";
  assert.equal(analysisFailureMessage(network), "网络连接中断，未能连上模型服务");
  assert.equal(analysisFailureMessage("LLM_REQUEST_TIMEOUT: 模型服务响应超时"), "分析超时，未在限定时间内完成");
  assert.equal(analysisFailureMessage("执行超时 (120s)"), "分析超时，未在限定时间内完成");
  assert.equal(analysisFailureMessage("LLM_REQUEST_FAILED: 模型服务请求失败"), "模型服务请求失败");
  assert.equal(isNetworkFailure("LLM_REQUEST_FAILED: 模型服务请求失败"), false);
  assert.equal(failureReasonSummary([
    { success: true }, { success: false, error: network }, { success: false, error: "执行超时 (120s)" },
  ]), "分析期间网络连接中断，部分分析超时；");
  assert.equal(failureReasonSummary([{ success: false, error: "LLM_REQUEST_FAILED: 模型服务请求失败" }]), "");
  assert.match(noResearchMessage([{ success: false, error: network }]), /网络连接中断.*确认网络恢复后手动重新分析/);
  assert.match(debateErrorMessage({ code: "ANALYSIS_NETWORK_UNAVAILABLE" }), /网络连接中断/);
});
