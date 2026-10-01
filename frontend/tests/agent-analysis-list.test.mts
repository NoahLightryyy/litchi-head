import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { AgentAnalysis } from "../lib/types/debate.ts";

// Compile the actual leaf component, without creating a public mock route or calling an LLM.
const componentUrl = new URL("../components/stock/agent-analysis-list.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(componentUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const componentModule = { exports: {} as { AgentAnalysisList: (props: { analyses: AgentAnalysis[] }) => unknown } };
new Function("require", "module", "exports", compiled)(createRequire(componentUrl), componentModule, componentModule.exports);
const render = (analyses: AgentAnalysis[]) => renderToStaticMarkup(createElement(componentModule.exports.AgentAnalysisList, { analyses }));
const good: AgentAnalysis = { agent_name: "master.fixture", skill_id: "fixture", skill_name: "测试价值流派", summary: "测试摘要", analysis: "测试完整论证", key_evidence: ["测试依据一", "测试依据二"], risk_warning: "测试风险", score: 67, rating: "B", confidence: 0.6, direction: "Bullish", success: true, latency_ms: 1 };

test("真实字段完整可读且模型置信度不标为胜率", () => {
  const html = render([good]);
  for (const text of ["测试价值流派", "测试摘要", "测试完整论证", "测试依据一", "测试风险", "60%", "非胜率"]) assert.ok(html.includes(text));
  assert.match(html, /<details/);
});

test("失败流派不把默认中性、零分或错误正文当投资结论", () => {
  const html = render([{ ...good, success: false, direction: "Neutral", score: 0, confidence: 0, error: "secret endpoint", analysis: "failed payload" }]);
  assert.match(html, /未完成的流派/);
  assert.match(html, /分析未成功/);
  for (const text of ["0/100", "0%", "secret endpoint", "failed payload", "测试摘要"]) assert.ok(!html.includes(text));
});

test("缺依据或风险明确缺失，非法数值不绘制，文本不得执行脚本", () => {
  const html = render([{ ...good, analysis: "<script>alert(1)</script>", key_evidence: [], risk_warning: null, confidence: NaN, score: Infinity }]);
  assert.match(html, /未提供独立列出的依据/);
  assert.match(html, /不代表没有风险/);
  assert.ok(!html.includes("NaN") && !html.includes("Infinity") && !html.includes("<script>"));
  assert.match(html, /&lt;script&gt;/);
});

test("空返回不合成流派或结论", () => {
  assert.match(render([]), /尚未返回任何流派分析/);
});
