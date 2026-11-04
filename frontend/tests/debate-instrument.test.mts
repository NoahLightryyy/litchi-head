import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as instrument from "../lib/debate-instrument.ts";
import * as errors from "../lib/debate-error.ts";
import * as sessions from "../lib/debate-session.ts";
import * as history from "../lib/debate-history.ts";
import * as limitations from "../lib/debate-limitations.ts";

const code = "560780";
test("ETF类型显式提交，缺类型旧结果只归股票，历史与结果缓存相互隔离", () => {
  assert.deepEqual(instrument.debateRequest(code, "设备ETF", "etf"), { stock_code: code, instrument_type: "etf", question: "设备ETF ETF 投资分析" });
  assert.equal(instrument.debateInstrumentMatches({ stock_code: code }, code, "stock"), true);
  assert.equal(instrument.debateInstrumentMatches({ stock_code: code }, code, "etf"), false);
  for (const data of [{ stock_code: "159915", instrument_type: "etf" }, { stock_code: code, instrument_type: "stock" }, { stock_code: code, instrument_type: null }]) {
    assert.equal(instrument.debateInstrumentMatches(data, code, "etf"), false);
  }
  assert.notDeepEqual(instrument.debateHistoryKey(code, "stock"), instrument.debateHistoryKey(code, "etf"));
  assert.notDeepEqual(instrument.debateResultKey("same-session", "stock"), instrument.debateResultKey("same-session", "etf"));
});

test("提交成功响应必须属于当前代码和类型，不能把旧股票会话用于基金结果", () => {
  const req = instrument.debateRequest(code, "设备ETF", "etf");
  const value = { session_id: "etf-session", status: "completed", stock_code: code, instrument_type: "etf" };
  assert.deepEqual(instrument.parseDebateRun(value, req), { session_id: "etf-session" });
  for (const replacement of [{ instrument_type: "stock" }, { instrument_type: undefined }, { stock_code: "159915" }, { status: "running" }, { session_id: "" }]) {
    assert.throws(() => instrument.parseDebateRun({ ...value, ...replacement }, req));
  }
  assert.equal(instrument.parseDebateRun({ ...value, instrument_type: "stock" }, { stock_code: code, question: "test" }).session_id, "etf-session");
});

function compile(path: string, overrides: Record<string, unknown>): Record<string, unknown> {
  const url = new URL(path, import.meta.url);
  const output = ts.transpileModule(readFileSync(url, "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const componentModule = { exports: {} as Record<string, unknown> };
  const require = createRequire(url);
  new Function("require", "module", "exports", output)((name: string) => name in overrides ? overrides[name] : require(name), componentModule, componentModule.exports);
  return componentModule.exports;
}

test("真实API消费者给请求和历史带ETF类型；读取历史不触发模型", async () => {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const moduleExports = compile("../lib/api/debate.ts", {
    "@/lib/debate-instrument": instrument,
    "./client": { api: {
      post: async (path: string, body: unknown) => { calls.push({ method: "POST", path, body }); return { session_id: "etf-session", stock_code: code, instrument_type: "etf", status: "completed" }; },
      get: async (path: string, body: unknown) => { calls.push({ method: "GET", path, body }); return [{ stock_code: code, instrument_type: "etf", session_id: "fund" }, { stock_code: code, session_id: "legacy" }]; },
    } },
  }) as {
    runDebate: (request: ReturnType<typeof instrument.debateRequest>) => Promise<{ session_id: string }>;
    fetchDebateHistory: (code: string, offset: number, kind: string) => Promise<{ session_id: string }[]>;
  };
  assert.deepEqual(await moduleExports.fetchDebateHistory(code, 50, "etf"), [{ stock_code: code, instrument_type: "etf", session_id: "fund" }]);
  assert.deepEqual(calls, [{ method: "GET", path: "/debate/history", body: { stock_code: code, instrument_type: "etf", offset: "50" } }]);
  const req = instrument.debateRequest(code, "设备ETF", "etf");
  assert.equal((await moduleExports.runDebate(req)).session_id, "etf-session");
  assert.deepEqual(calls[1], { method: "POST", path: "/debate/run", body: req });
});

function renderDebate(kind: "stock" | "etf", recordType: "stock" | "etf" | undefined, resultType: "stock" | "etf" | undefined, historyPending = false) {
  let runs = 0;
  const hookTypes: unknown[] = [];
  const entryPlanProps: { result: unknown; instrumentType: string }[] = [];
  const record = { session_id: "saved", stock_code: code, instrument_type: recordType, status: "completed", created_at: "2026-10-26T08:00:00+08:00" };
  const result = { session_id: "saved", stock_code: code, instrument_type: resultType, vote_summary: {}, analyses: [] };
  const panel = compile("../components/stock/debate-panel.tsx", {
    "@/lib/hooks/use-debate": {
      useRunDebate: () => ({ trigger: () => { runs++; }, sessionId: null, running: false }),
      useDebateHistory: (_code: string, _offset: number, type: string) => { hookTypes.push(type); return { data: historyPending ? undefined : [record], isPending: historyPending, isError: false, refetch: () => {} }; },
      useDebateResult: (_session: string, _active: boolean, type: string) => { hookTypes.push(type); return { data: result, isError: false, isTimedOut: false }; },
    },
    "@/lib/debate-instrument": instrument, "@/lib/debate-error": errors, "@/lib/debate-session": sessions,
    "@/lib/debate-history": history,
    "./debate-data-notice": compile("../components/stock/debate-data-notice.tsx", { "@/lib/debate-limitations": limitations }),
    "./technical-supplement-panel": { TechnicalSupplementPanel: () => createElement("div", null, "technical-supplement-result") },
    "./horizon-research": { HorizonResearch: () => createElement("div", null, "horizon-result") },
    "./entry-plan-panel": { EntryPlanPanel: (props: { result: unknown; instrumentType: string }) => { entryPlanProps.push(props); return createElement("div", null, "entry-plan-result"); } },
    "./agent-analysis-list": { AgentAnalysisList: () => createElement("div", null, "agent-result") },
  }).DebatePanel as (props: never) => unknown;
  const html = renderToStaticMarkup(createElement(panel, { stockCode: code, stockName: "设备ETF", instrumentType: kind } as never));
  return { html, runs, hookTypes, entryPlanProps, result };
}

test("ETF面板自动读取历史但不提交，错误类型结果不能显示成基金结论", () => {
  const good = renderDebate("etf", "etf", "etf");
  assert.equal(good.runs, 0);
  assert.deepEqual(good.hookTypes, ["etf", "etf"]);
  assert.match(good.html, /horizon-result/);
  assert.match(good.html, /围绕 ETF 主题/);
  assert.doesNotMatch(good.html, /technical-supplement-result/);
  assert.deepEqual(good.entryPlanProps, [{ result: good.result, instrumentType: "etf" }]);
  assert.ok(good.html.indexOf("entry-plan-result") < good.html.indexOf("horizon-result"));
  for (const resultType of ["stock", undefined] as const) {
    const bad = renderDebate("etf", "etf", resultType);
    assert.doesNotMatch(bad.html, /horizon-result|agent-result/);
    assert.equal(bad.entryPlanProps.length, 0);
    assert.match(bad.html, /本次分析失败/);
  }
  assert.doesNotMatch(renderDebate("etf", undefined, undefined).html, /horizon-result|查看结果/);
  const stock = renderDebate("stock", undefined, undefined);
  assert.match(stock.html, /horizon-result/);
  assert.match(stock.html, /technical-supplement-result/);
  assert.ok(stock.html.indexOf("technical-supplement-result") < stock.html.indexOf("horizon-result"));
});

test("ETF错误不提示恢复股票财务或等待连续竞价", () => {
  assert.match(errors.debateErrorMessage({ code: "ETF_NOT_FOUND" }, "etf"), /确认代码/);
  assert.match(errors.debateErrorMessage({ code: "INSTRUMENT_TYPE_MISMATCH" }), /ETF 详情页/);
  const message = errors.debateErrorMessage({ code: "EVIDENCE_INCOMPLETE", detail: { capability: "etf_research" } }, "etf");
  assert.match(message, /刷新行情、K线或相关资料/);
  assert.doesNotMatch(message, /股票名称|连续竞价/);
});

test("初次历史读取完成前禁用触发，避免尚未发现运行会话时重复付费", () => {
  for (const kind of ["stock", "etf"] as const) {
    const pending = renderDebate(kind, kind, kind, true);
    const button = [...pending.html.matchAll(/<button([^>]*)>([\s\S]*?)<\/button>/g)].find(match => match[2].includes("读取记录…"));
    assert.ok(button);
    assert.match(button[1], /disabled=""/);
    assert.equal(pending.runs, 0);
    const ready = renderDebate(kind, kind, kind);
    const trigger = [...ready.html.matchAll(/<button([^>]*)>([\s\S]*?)<\/button>/g)].find(match => match[2].includes("帮我看看机会和风险"));
    assert.ok(trigger);
    assert.doesNotMatch(trigger[1], /\sdisabled=/);
  }
});

test("ETF详情按报价、K线、辩论、资料排序，辩论显式使用etf且来源折叠", () => {
  let debateProps: unknown;
  const view = compile("../app/etf/[code]/page.tsx", {
    "next/navigation": { useParams: () => ({ code }) },
    "next/link": { default: (props: { href: string; children: unknown }) => createElement("a", { href: props.href }, props.children as never) },
    "@tanstack/react-query": { useQuery: () => ({ data: {
      identity: { code, name: "设备ETF", symbol: `sh${code}`, exchange: "SH" },
      quote: { price: 0.749, previous_close: 0.781, change: -0.032, change_pct: -4.1, open: 0.781, high: 0.790, low: 0.747, quoted_at: "2026-10-26T15:00:00+08:00", source_name: "设备ETF" },
      limitations: [], catalog_fetched_at: "2026-10-27T08:00:00+08:00", source_url: "https://example.org/catalog",
    }, isPending: false, isError: false, isFetching: false }) },
    "@/lib/api/client": {}, "@/lib/etf-display": {},
    "@/components/etf/etf-kline-panel": { EtfKlinePanel: () => createElement("div", null, "chart-component") },
    "@/components/stock/debate-panel": { DebatePanel: (props: unknown) => { debateProps = props; return createElement("div", null, "debate-component"); } },
    "@/components/research/research-context": { ResearchContext: () => createElement("div", null, "research-component") },
  }).default as () => unknown;
  const html = renderToStaticMarkup(createElement(view));
  assert.deepEqual(debateProps, { stockCode: code, stockName: "设备ETF", instrumentType: "etf" });
  assert.ok(html.indexOf("场内交易价格") < html.indexOf("chart-component"));
  assert.ok(html.indexOf("chart-component") < html.indexOf("debate-component"));
  assert.ok(html.indexOf("debate-component") < html.indexOf("research-component"));
  assert.match(html, /0.749/);
  assert.match(html, /href="#etf-debate"/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
});
