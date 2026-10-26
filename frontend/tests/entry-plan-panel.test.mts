import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as entryPlan from "../lib/entry-plan.ts";
import * as sizing from "../lib/entry-plan-sizing.ts";
import * as instrument from "../lib/debate-instrument.ts";
import type { EntryPlanContentProps } from "../components/stock/entry-plan-panel.tsx";

function fixture(): entryPlan.EntryPlanResult {
  return {
    schema_version: 1, session_id: "session-1", source_session_id: "session-1", stock_code: "688648", instrument_type: "stock", stock_name: "中邮科技",
    source_research_generated_at: "2026-10-26T15:30:00+08:00", generated_at: "2026-10-27T09:00:00+08:00", model: "test-model",
    purpose: "conditional_research_plan", status_basis: "ai_review_of_dated_evidence", cached: false, gaps: ["没有持续监测"],
    evidence: [{ id: "quote-1", kind: "quote", title: "本股行情", data_time: "2026-10-26 15:00", content: "价格10元" }],
    plans: (["short", "medium", "long"] as const).map((horizon, index) => ({
      horizon, status: "waiting", summary: `周期${index + 1}条件摘要`,
      conditions: [
        { condition: "价格站稳", status: "met", explanation: "本次行情已站稳", evidence_ids: ["quote-1"] },
        { condition: "放量确认", status: "unmet", explanation: "成交量不足", evidence_ids: ["quote-1"] },
        { condition: "财报确认", status: "unknown", explanation: "缺少新一期财报", evidence_ids: ["quote-1"] },
      ],
      entry_low: 10 + index, entry_high: 11 + index, stop_loss: 9 + index, price_basis: `周期${index + 1}价格依据`, price_evidence_ids: ["quote-1"],
      invalidation: ["跌破支撑则暂停后续买入"], batches: [{ budget_pct: 30, trigger: "首次站稳时" }, { budget_pct: 70, trigger: "回踩后确认时" }],
      position_note: "仓位由输入资金测算", limitations: ["条件可能发生变化"],
    })),
  };
}

const componentUrl = new URL("../components/stock/entry-plan-panel.tsx", import.meta.url);
const componentModule = { exports: {} as { EntryPlanContent: ComponentType<EntryPlanContentProps> } };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(componentUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)((id: string) => {
  if (id === "@/lib/entry-plan") return entryPlan;
  if (id === "@/lib/entry-plan-sizing") return sizing;
  if (id === "@/lib/debate-instrument") return instrument;
  return createRequire(componentUrl)(id);
}, componentModule, componentModule.exports);
const render = (props: Partial<EntryPlanContentProps> = {}) => renderToStaticMarkup(createElement(componentModule.exports.EntryPlanContent, {
  name: "中邮科技", data: null, horizon: "short", loading: false, reading: false, generating: false, offline: false,
  error: null, canGenerate: true, onHorizon: () => {}, onRead: () => {}, onGenerate: () => {}, ...props,
}));

test("旧辩论无计划时明确提供手动生成入口，不把旧走势改名买点", () => {
  const html = render();
  assert.match(html, /这份辩论尚无入场计划/);
  assert.match(html, /生成条件计划/);
  assert.match(html, /不重跑辩论/);
  assert.match(html, /失败后不会自动重试生成/);
  assert.doesNotMatch(html, /本地资金与风险试算|已确认买点/);
});

test("加载、离线、生成中及失败刷新保留同会话计划", () => {
  assert.match(render({ loading: true, reading: true, canGenerate: false }), /正在读取本次辩论的入场计划/);
  const offline = render({ data: fixture(), offline: true });
  assert.match(offline, /保留上次计划，资金试算仍可使用/);
  assert.match(offline, /disabled="">更新条件计划/);
  const failed = render({ data: fixture(), error: "上游暂时不可用" });
  assert.match(failed, /本次更新未完成，保留上次计划/);
  assert.match(failed, /上游暂时不可用/);
  assert.match(failed, /周期1条件摘要/);
  const generating = render({ data: fixture(), generating: true });
  assert.match(generating, /下方暂保留上次计划/);
  assert.match(generating, /周期1条件摘要/);
});

test("条件分别显示已满足、未满足和无法判断，consider不宣称确认买点", () => {
  const html = render({ data: fixture() });
  assert.match(html, /按所示数据已满足/);
  assert.match(html, /尚未满足/);
  assert.match(html, /尚无法判断/);
  assert.match(html, /AI 按所示数据核对，未持续监测/);
  assert.match(html, /停止入场或暂停后续批次的条件/);
  const value = fixture(); value.plans[0].status = "consider";
  value.plans[0].conditions.forEach((condition) => { condition.status = "met"; });
  const consider = render({ data: value });
  assert.match(consider, /可关注入场条件/);
  assert.match(consider, /仍需核对最新行情与条件/);
  assert.doesNotMatch(consider, /买点已确认|立即买入|胜率/);
});

test("各周期展示自己的候选价格与分批触发，证据限制默认折叠", () => {
  const short = render({ data: fixture(), horizon: "short" });
  const medium = render({ data: fixture(), horizon: "medium" });
  assert.match(short, /周期1价格依据/);
  assert.doesNotMatch(short, /周期2价格依据/);
  assert.match(medium, /周期2价格依据/);
  assert.doesNotMatch(medium, /周期1价格依据/);
  assert.match(medium, /value="12"/);
  assert.match(medium, /value="10"/);
  assert.match(short, /首次站稳时/);
  assert.match(short, /回踩后确认时/);
  assert.match(short, /本次计划预算；不代表账户总资产仓位/);
  assert.match(short, /查看资料时间、依据与限制/);
  assert.doesNotMatch(short, /<details[^>]*open/);
  assert.match(short, /数据时间 2026-10-26 15:00/);
  assert.match(short, /行情数据时间：报价 2026-10-26 15:00/);
  assert.ok(short.indexOf("计划使用的行情时间") < short.indexOf("<details"));
  assert.match(short, /条件可能发生变化/);
});

test("账户资金无默认值，价格只作可编辑试算且无价格时仍可手动填写", () => {
  const html = render({ data: fixture() });
  assert.equal((html.match(/value=""/g) ?? []).length, 5);
  assert.match(html, /资金只在当前页面计算，不发送给 AI 或服务器/);
  assert.match(html, /切换周期或更新计划会清空试算输入/);
  assert.match(html, /手动改价仅影响试算，不改变上方 AI 条件状态/);
  assert.match(html, /此次新增可承受亏损金额/);
  assert.match(html, /各批按同一输入价格估算；后续批次价格变化时须重新计算/);
  assert.match(html, /现有持仓市值（元，无持仓请填 0）/);
  const data = fixture(); Object.assign(data.plans[0], { entry_low: null, entry_high: null, stop_loss: null, price_evidence_ids: [] });
  const manual = render({ data });
  assert.equal((manual.match(/value=""/g) ?? []).length, 7);
  assert.match(manual, /可手动填写价格做情景试算/);
  assert.match(manual, /计算新增仓位与分批金额/);
  assert.doesNotMatch(manual, /需先取得当前标的证据包|暂不能给出可买数量/);
});
