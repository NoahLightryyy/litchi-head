import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as interpretation from "../lib/related-interpretation.ts";
import type { RelatedInterpretationContentProps } from "../components/research/related-interpretation-panel.tsx";
import type { RelatedResearchRequest } from "../lib/related-research.ts";

function fixture(count = 1): interpretation.RelatedInterpretationResult {
  const sources = Array.from({ length: count + 1 }, (_, index) => ({
    id: `source-${index}`, title: `资料${index + 1}原文`, url: `https://example.org/${index}`, publisher: "来源单位", published_at: "2025-10-01", excerpt: "明确记载设备更新，尚无公司订单信息。",
    source: index === 0 ? "policy_archive" as const : "news_archive" as const, category: "policy" as const, relevance: "topic" as const, matched_keywords: ["设备"], reason: "主题相关",
  }));
  const inference = (text: string) => ({ text, basis: "inference" as const });
  return {
    schema_version: 1, subject_kind: "stock", subject_id: "688648", subject_name: "中邮科技", query: "", generated_at: "2026-10-27T12:00:00+08:00", model: "test", prompt_version: "v1", review_status: "ai_unreviewed", purpose: "related_material_context_only", status: "interpreted", snapshot_sha256: "a".repeat(64),
    snapshot: { schema_version: 1, subject_kind: "stock", subject_id: "688648", subject_name: "中邮科技", query: "", status: "ready", keywords: [{ term: "设备", origin: "business" }], data: sources, sources: [{ source: "policy_archive", status: "ok", message: "" }], searched_at: "2026-10-27T11:59:00+08:00", window_days: 365, limitations: ["政策档案只保留摘要"] },
    analysis: { overview: "这批资料谈到设备更新，应继续观察实际订单。", events: sources.slice(0, count).map((source, index) => ({
      title: `设备更新事件${index + 1}`, source_ids: [source.id], summary: { text: "资料记载设备更新安排，尚无公司订单信息。", basis: "reported", quotes: [{ source_id: source.id, field: "excerpt", quote: "明确记载设备更新" }] }, impact_direction: "mixed",
      impact_path: inference("需求可能向设备商传导"), affected_scope: inference("涉及物流设备环节"), duration: inference("持续期取决于落地进度"), market_reaction: inference("情绪可能先变化，未观察实际行情反应"), business_realization: inference("订单、交付再到收入"), subject_relation: inference("主营相关不等于实际获得订单"), watchpoints: ["核查订单公告"],
    })), excluded_sources: [{ source_id: sources[count].id, reason: "弱相关，暂不展开" }], limitations: ["未读取完整报道正文"] },
  };
}
const componentUrl = new URL("../components/research/related-interpretation-panel.tsx", import.meta.url);
const componentModule = { exports: {} as { RelatedInterpretationContent: ComponentType<RelatedInterpretationContentProps> } };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(componentUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)((id: string) => id === "@/lib/related-interpretation" ? interpretation : createRequire(componentUrl)(id), componentModule, componentModule.exports);
const render = (props: Partial<RelatedInterpretationContentProps> = {}) => renderToStaticMarkup(createElement(componentModule.exports.RelatedInterpretationContent, {
  data: null, query: "", loading: false, reading: false, generating: false, offline: false, error: null, canGenerate: true,
  onRead: () => {}, onGenerate: () => {}, ...props,
}));

test("空解读、读取中、离线与生成中分别展示，不要求正式证据包", () => {
  const empty = render();
  assert.match(empty, /尚无当前检索条件的解读/);
  assert.match(empty, /AI 生成解读/);
  assert.match(empty, /读取已存解读不调用模型/);
  assert.doesNotMatch(empty, /证据包|账户|资金预算/);
  assert.match(render({ loading: true, reading: true, canGenerate: false }), /正在读取本标的、当前检索条件/);
  assert.match(render({ offline: true }), /当前离线/);
  assert.match(render({ generating: true }), /正在重新检索相关资料并整理事件与影响/);
});

test("更新失败或离线保留旧解读、生成时间和快照来源", () => {
  const data = fixture();
  const failed = render({ data, error: "资料服务暂不可用" });
  assert.match(failed, /保留上次成功解读，生成时间未更新/);
  assert.match(failed, /设备更新事件1/);
  assert.match(failed, /资料1原文/);
  const offline = render({ data, offline: true });
  assert.match(offline, /保留已保存解读和原资料快照/);
  assert.match(offline, /disabled="">AI 更新解读/);
  assert.match(offline, /复制研究要点/);
  const generating = render({ data, generating: true });
  assert.match(generating, /保留上次成功解读/);
  assert.match(generating, /设备更新事件1/);
});

test("读取失败保留错误说明并开放显式重建，离线时仍禁用", () => {
  const state = { readFailed: true, canGenerate: true, error: "已保存结果校验失败" };
  const html = render(state);
  assert.match(html, /已保存结果校验失败/);
  const rebuild = [...html.matchAll(/<button([^>]*)>([^<]*)<\/button>/g)].find((match) => match[2] === "AI 重新生成");
  assert.ok(rebuild);
  assert.doesNotMatch(rebuild[1], /\sdisabled=/);
  assert.match(render({ ...state, offline: true }), /disabled="">AI 重新生成/);
});

test("真实面板仅显式生成，成功时先取消同键旧读取再写入新结果", async () => {
  const require = createRequire(componentUrl);
  const request: RelatedResearchRequest = { kind: "stock", code: "688648", name: "中邮科技", q: "" };
  const mutationCalls: boolean[] = [], generationCalls: boolean[] = [];
  let readFailed = true, online = true, cached: interpretation.RelatedInterpretationResult | undefined;
  let mutationFn: ((refresh: boolean) => Promise<interpretation.RelatedInterpretationResult>) | undefined;
  let onSuccess: ((result: interpretation.RelatedInterpretationResult) => Promise<void>) | undefined;
  let finishCancel: (() => void) | undefined, failCancellation = false;
  const cacheEvents: string[] = [], cancelled: unknown[] = [], writes: unknown[] = [];
  const consumer = { exports: {} as { RelatedInterpretationPanel: (props: { request: RelatedResearchRequest }) => ReactElement } };
  new Function("require", "module", "exports", ts.transpileModule(readFileSync(componentUrl, "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText)((id: string) => {
    if (id === "react") return { ...require("react"), useSyncExternalStore: () => online };
    if (id === "@/lib/related-interpretation") return { ...interpretation, generateRelatedInterpretation: async (_request: RelatedResearchRequest, refresh: boolean) => { generationCalls.push(refresh); return fixture(); } };
    if (id === "@tanstack/react-query") return {
      useQueryClient: () => ({
        cancelQueries: (filters: unknown) => {
          cancelled.push(filters); cacheEvents.push("cancel-start");
          if (failCancellation) return Promise.reject(new Error("取消失败"));
          return new Promise<void>((resolve) => { finishCancel = () => { cacheEvents.push("cancel-end"); resolve(); }; });
        },
        setQueryData: (key: unknown, result: interpretation.RelatedInterpretationResult) => { cacheEvents.push("write"); writes.push({ key, result }); },
      }),
      useQuery: () => ({ data: cached, isPending: false, isFetching: false, isPaused: false, isError: readFailed, isSuccess: !readFailed, error: readFailed ? new Error("读取失败") : null }),
      useMutation: (options: { mutationFn: typeof mutationFn; onSuccess: typeof onSuccess }) => { mutationFn = options.mutationFn; onSuccess = options.onSuccess; return { isPending: false, error: null, mutate: (refresh: boolean) => mutationCalls.push(refresh) }; },
    };
    return require(id);
  }, consumer, consumer.exports);
  const view = () => {
    const wrapper = consumer.exports.RelatedInterpretationPanel({ request });
    return (wrapper.type as (props: unknown) => ReactElement<RelatedInterpretationContentProps>)(wrapper.props).props;
  };
  const descriptor = Object.getOwnPropertyDescriptor(navigator, "onLine");
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  try {
    const failed = view();
    assert.equal(failed.canGenerate, true); assert.equal(failed.readFailed, true);
    assert.deepEqual(mutationCalls, []); assert.deepEqual(generationCalls, []);
    failed.onGenerate(); assert.deepEqual(mutationCalls, [true]);
    assert.ok(mutationFn); await mutationFn(mutationCalls[0]);
    assert.deepEqual(generationCalls, [true]);

    readFailed = false;
    view().onGenerate(); assert.deepEqual(mutationCalls, [true, false]);
    cached = fixture();
    view().onGenerate(); assert.deepEqual(mutationCalls, [true, false, true]);

    assert.ok(onSuccess);
    const generated = fixture(), pending = onSuccess(generated);
    assert.deepEqual(cancelled, [{ queryKey: interpretation.relatedInterpretationKey(request), exact: true }]);
    assert.deepEqual(cacheEvents, ["cancel-start"]); assert.deepEqual(writes, []);
    assert.ok(finishCancel); finishCancel(); await pending;
    assert.deepEqual(cacheEvents, ["cancel-start", "cancel-end", "write"]);
    assert.deepEqual(writes, [{ key: interpretation.relatedInterpretationKey(request), result: generated }]);

    failCancellation = true;
    const warn = console.warn, warnings: unknown[] = [];
    console.warn = (message: unknown) => { warnings.push(message); };
    try { await onSuccess(generated); } finally { console.warn = warn; }
    assert.equal(warnings.length, 1);
    assert.equal(writes.length, 2);
    assert.deepEqual(cacheEvents.slice(-2), ["cancel-start", "write"]);

    readFailed = true; online = false;
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    assert.equal(view().offline, true);
    await assert.rejects(async () => mutationFn!(true), /当前离线/);
    assert.deepEqual(generationCalls, [true]);
  } finally {
    if (descriptor) Object.defineProperty(navigator, "onLine", descriptor);
    else Reflect.deleteProperty(navigator, "onLine");
  }
});

test("通俗概况、六个推断维度、核查点及原始发布时间直接可见", () => {
  const html = render({ data: fixture() });
  for (const text of ["先读这段", "资料说了什么", "产业怎样受影响", "涉及哪些范围", "影响可能持续多久", "市场情绪反应", "经营兑现节奏", "与当前标的的关系", "接下来核查什么", "核查订单公告", "AI 推断", "未经人工复核"]) assert.ok(html.includes(text));
  assert.match(html, /发布 2025-10-01/);
  assert.match(html, /href="https:\/\/example.org\/0"/);
  assert.match(html, /生成于 2026\/10\/27 12:00:00/);
  assert.match(html, /资料快照检索于 2026\/10\/27 11:59:00/);
  assert.match(html, /档案摘要/);
  assert.doesNotMatch(html, /政策原文已核验|确定受益|<details[^>]*\sopen(?:[=>\s])/);
});

test("来源时刻统一北京时间，日期和未知文本保留，排除资料同样处理", () => {
  const data = fixture(3);
  data.snapshot.data[0].published_at = "2026-05-21T11:51:55+00:00";
  data.snapshot.data[1].published_at = "2026-05-20";
  data.snapshot.data[2].published_at = "时间未提供";
  data.snapshot.data[3].published_at = "2026-05-19T20:03:04Z";
  const html = render({ data });
  assert.match(html, /发布 2026\/5\/21 19:51:55/);
  assert.match(html, /发布 2026-05-20/);
  assert.match(html, /发布 时间未提供/);
  assert.match(html, /发布 2026\/5\/20 04:03:04/);
  assert.match(html, /4 篇资料 · 3 个事件/);
  assert.equal((html.match(/北京时间/g) ?? []).length, 1);
  assert.doesNotMatch(html, /T11:51:55|T20:03:04|Invalid Date/);
});

test("前三个事件默认展示，余下事件、引用细节和排除原因折叠", () => {
  const html = render({ data: fixture(4) });
  assert.match(html, /展开其余 1 个事件/);
  assert.match(html, /设备更新事件4/);
  assert.ok(html.indexOf("设备更新事件3") < html.indexOf("展开其余 1 个事件"));
  assert.ok(html.indexOf("设备更新事件4") > html.indexOf("展开其余 1 个事件"));
  assert.match(html, /查看引用片段与原始资料范围/);
  assert.match(html, /弱相关，暂不展开/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
});

test("新检索不替换旧解读来源，提示资料变化并保持当前关键词边界", () => {
  const data = fixture(); const current = structuredClone(data.snapshot);
  current.data[0].title = "刚取得的新标题"; current.data[0].url = "https://example.org/new";
  const html = render({ data, current });
  assert.match(html, /当前检索资料已变化/);
  assert.match(html, /下方解读仍基于原资料快照/);
  assert.match(html, /资料1原文/);
  assert.doesNotMatch(html, /刚取得的新标题|example.org\/new/);
  assert.match(html, /自动提词的已存解读会供后续辩论参考/);
  const custom = fixture(); custom.query = "智能物流"; custom.snapshot.query = "智能物流";
  const customHtml = render({ data: custom, query: "智能物流" });
  assert.match(customHtml, /自定关键词的解读可复制到后续研究中/);
  assert.doesNotMatch(customHtml, /会供后续辩论参考/);
});

test("全部弱相关时展示排除结果，来源内容始终作为文本渲染", () => {
  const data = fixture(); data.analysis.events = []; data.status = "no_relevant_events";
  data.analysis.excluded_sources.push({ source_id: "source-0", reason: "主题不足" });
  assert.match(render({ data }), /没有适合展开的相关事件/);
  const unsafe = fixture(); unsafe.analysis.events[0].summary.text = "<script>window.evil()</script>";
  assert.match(render({ data: unsafe }), /&lt;script&gt;/);
  assert.doesNotMatch(render({ data: unsafe }), /<script>/);
});
