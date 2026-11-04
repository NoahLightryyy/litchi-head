import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as notices from "../lib/debate-limitations.ts";

const url = new URL("../components/stock/debate-data-notice.tsx", import.meta.url);
const component = { exports: {} as { DebateDataNotice: ComponentType<{ result: notices.DebateNoticeInput }> } };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(url, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)((name: string) => name === "@/lib/debate-limitations" ? notices : createRequire(url)(name), component, component.exports);
const render = (result: notices.DebateNoticeInput) => renderToStaticMarkup(createElement(component.exports.DebateDataNotice, { result }));

test("历史范围原文只在默认折叠的详情中，正常说明不用警告色或实时告警角色", () => {
  const note = "sina 新闻样本时间范围 2026-10-26T17:58:32+08:00 至 2026-10-27T01:09:16+08:00，匹配 0 条；未覆盖完整近 3 天。";
  const html = render({ evidence_limitations: [{ capability: "news", research_note: note, source_statuses: { sina: "stale" }, error_codes: ["rolling_window_not_fully_covered"] }] });
  const summary = html.slice(0, html.indexOf("<details"));
  assert.match(summary, /本次新闻样本未匹配到相关报道/);
  assert.match(summary, /未生成交易执行指令/);
  assert.doesNotMatch(summary, /sina|2026-10-26T|rolling_window|本次研究的限制|amber|role="(?:status|alert)"/);
  assert.match(html, /查看来源与诊断详情/);
  assert.ok(html.indexOf(note) > html.indexOf("<details"));
  assert.match(html, /sina：未满足实时性或覆盖要求/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
});

test("真实数据冲突、分析失败和评审缺失不折叠，危险数据优先显示", () => {
  const html = render({ evidence_limitations: [{ capability: "realtime_quote", error_codes: ["quote_price_conflict"] }], analyses: [{ success: true }, { success: false }], review_report: null });
  const summary = html.slice(0, html.indexOf("<details"));
  assert.match(summary, /数据存在冲突或校验异常/);
  assert.match(summary, /bg-accent-red/);
  assert.match(summary, /未取得有效独立评审/);
  assert.match(summary, /1 位分析未成功/);
  assert.ok(summary.indexOf("数据存在冲突") < summary.indexOf("独立评审"));
  assert.match(html, /此历史结果未保存进一步的范围说明/);
});

test("无说明不占空间，未知限制仍提示，原始来源内容按文本转义", () => {
  assert.equal(render({}), "");
  const html = render({ evidence_limitations: [{ capability: "unknown", research_note: "<script>evil()</script>" }] });
  assert.match(html.slice(0, html.indexOf("<details")), /部分研究资料存在限制/);
  assert.match(html, /&lt;script&gt;evil\(\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
