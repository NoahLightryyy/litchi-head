import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryObserver, focusManager, onlineManager } from "@tanstack/react-query";
import ts from "typescript";
import * as policyCapital from "../lib/policy-capital.ts";
import {
  fetchRelatedResearch, parseRelatedResearch, requireRelatedResearch, relatedResearchKey, relatedResearchRequest, relatedResearchQueryPolicy,
  type RelatedResearchRequest, type RelatedResearchResult,
} from "../lib/related-research.ts";

const request: RelatedResearchRequest = { kind: "etf", code: "560780", name: "半导体设备ETF广发", q: "" };
const fixture = (query: RelatedResearchRequest = request): RelatedResearchResult => ({
  schema_version: 1, subject_kind: query.kind, subject_id: query.code, subject_name: query.name, query: query.q,
  status: "ready", keywords: [{ term: "半导体", origin: "name" }, { term: "集成电路", origin: "expanded" }],
  data: [
    { id: "report-1", title: "设备主题报道", url: "https://example.org/report", publisher: "测试报道来源", published_at: "2026-10-22T08:30:00+08:00", excerpt: "报道摘录", source: "news_archive", category: "report", relevance: "topic", matched_keywords: ["半导体"], reason: "正文命中半导体主题" },
    { id: "policy-1", title: "集成电路政策报道", url: "https://example.org/policy", publisher: "测试政策报道来源", published_at: "2026-10-20", excerpt: "政策报道摘录", source: "news_archive", category: "policy", relevance: "topic", matched_keywords: ["集成电路"], reason: "标题命中集成电路主题" },
  ],
  sources: [{ source: "news_archive", status: "ok", message: "" }, { source: "policy_archive", status: "ok", message: "" }, { source: "company_profile", status: "not_requested", message: "ETF 按名称检索" }],
  searched_at: "2026-10-26T20:00:00+08:00", window_days: 365, limitations: ["范围为已入库资料"],
});

test("绑定标的、名称与提交的查询，异步 ETF 名称更新也隔离缓存", () => {
  assert.equal(parseRelatedResearch(fixture(), request).subject_id, "560780");
  const normalized = relatedResearchRequest({ kind: "etf", code: "560780", name: " 半导体设备ETF广发 " }, " 集成电路 ");
  assert.equal(normalized.name, request.name);
  assert.equal(normalized.q, "集成电路");
  for (const changed of [{ kind: "stock" as const }, { code: "512480" }, { name: "560780" }, { q: "新能源" }]) {
    const other = { ...request, ...changed };
    assert.notDeepEqual(relatedResearchKey(other), relatedResearchKey(request));
    assert.throws(() => parseRelatedResearch(fixture(), other));
  }
  for (const kind of ["stock", "etf", "sector"] as const) {
    const query = { ...request, kind, code: kind === "sector" ? "sina:hangye_BK01" : request.code };
    assert.equal(parseRelatedResearch(fixture(query), query).subject_kind, kind);
  }
});

test("检索契约保留来源与日期，拒绝错版、伪链接和矛盾状态", () => {
  for (const replacement of [{ schema_version: 2 }, { window_days: 30 }, { status: "verified" }, { status: "empty" }, { searched_at: "2026-10-26T20:00:00" }, { keywords: [{ term: "", origin: "user" }] }]) {
    assert.throws(() => parseRelatedResearch({ ...fixture(), ...replacement }, request));
  }
  for (const replacement of [{ url: "javascript:alert(1)" }, { url: "https://user:password@example.org" }, { published_at: "" }, { published_at: "2026-10-26T13:00:00" }, { source: "official" }, { category: "verified_policy" }, { relevance: "beneficiary" }, { matched_keywords: [] }, { excerpt: "字".repeat(601) }]) {
    const value = fixture();
    assert.throws(() => parseRelatedResearch({ ...value, data: [{ ...value.data[0], ...replacement }] }, request));
  }
  assert.throws(() => parseRelatedResearch({ ...fixture(), data: [fixture().data[0], fixture().data[0]] }, request));
  assert.equal(parseRelatedResearch({ ...fixture(), status: "empty", data: [] }, request).data.length, 0);
  const shortQuery = { ...request, q: "铜" };
  assert.equal(parseRelatedResearch({ ...fixture(shortQuery), keywords: [{ term: "铜", origin: "user" }] }, shortQuery).keywords[0].term, "铜");
});

test("只读 GET 保留 422/503 的可操作详情，不创建研究任务", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  const calls: { url: string; method?: string }[] = [];
  try {
    for (const status of [422, 503]) {
      const message = status === 422 ? "请输入有效检索词，不能仅使用分隔符。" : "相关资料检索暂不可用，请重试。";
      globalThis.fetch = async (url, init) => {
        calls.push({ url: String(url), method: init?.method });
        return new Response(JSON.stringify({ detail: message }), { status });
      };
      await assert.rejects(fetchRelatedResearch(request, controller.signal), { message });
    }
    assert.equal(calls.length, 2);
    for (const call of calls) {
      assert.match(call.url, /\/research\/related\?/);
      assert.equal(call.method, undefined);
      assert.doesNotMatch(call.url, /\/jobs|execution-preview/);
    }
  } finally { globalThis.fetch = original; }
});

test("HTTP 200 不可用响应保留同查询旧资料，空命中和换查询不借用旧列表", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
  let response = fixture();
  const options = (query: RelatedResearchRequest = request) => ({
    queryKey: relatedResearchKey(query), ...relatedResearchQueryPolicy,
    queryFn: async () => requireRelatedResearch(response, query),
  });
  try {
    const old = await client.fetchQuery(options());
    const observer = new QueryObserver(client, options());
    response = { ...fixture(), status: "unavailable", data: [] };
    const failed = await observer.refetch();
    assert.equal(failed.isError, true);
    assert.deepEqual(failed.data, old);
    response = { ...fixture(), status: "empty", data: [] };
    assert.equal((await observer.refetch()).data?.data.length, 0);
    observer.setOptions(options({ ...request, q: "光伏" }));
    assert.equal(observer.getCurrentResult().data, undefined);
    assert.equal(observer.getCurrentResult().isPending, true);
    observer.destroy();
  } finally { client.clear(); }
});

test("重新聚焦或联网不自动重复检索，失败不循环重试", async () => {
  const client = new QueryClient();
  client.mount();
  let calls = 0;
  const observer = new QueryObserver(client, {
    queryKey: relatedResearchKey(request), ...relatedResearchQueryPolicy, staleTime: 0,
    queryFn: async () => { calls++; throw new Error("资料源离线"); },
  });
  const stop = observer.subscribe(() => {});
  try {
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(calls, 1);
    focusManager.setFocused(false); focusManager.setFocused(true);
    onlineManager.setOnline(false); onlineManager.setOnline(true);
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(calls, 1);
    assert.equal(observer.getCurrentResult().isError, true);
  } finally { stop(); observer.destroy(); client.unmount(); client.clear(); focusManager.setFocused(undefined); onlineManager.setOnline(true); }
});

function compileView(path: string, overrides: Record<string, unknown> = {}) {
  const url = new URL(path, import.meta.url);
  const compiled = ts.transpileModule(readFileSync(url, "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const componentModule = { exports: {} as Record<string, (props: never) => unknown> };
  const require = createRequire(url);
  new Function("require", "module", "exports", compiled)((name: string) => name in overrides ? overrides[name] : require(name), componentModule, componentModule.exports);
  return componentModule.exports;
}
const content = compileView("../components/research/related-research-content.tsx").RelatedResearchContent;
const render = (props: { data?: RelatedResearchResult; pending?: boolean; failed?: boolean; paused?: boolean; error?: string } = {}) => renderToStaticMarkup(createElement(content, {
  pending: false, failed: false, paused: false, onKeyword: () => {}, ...props,
} as never));

test("政策候选在报道前独立显示，保留发布原文日期、来源与匹配原因", () => {
  const html = render({ data: fixture() });
  assert.ok(html.indexOf("政策相关资料") < html.indexOf("设备主题报道"));
  for (const text of ["集成电路政策报道", "测试政策报道来源", "发布 2026-10-20", "2026-10-22T08:30:00+08:00", "正文命中半导体主题", "匹配词：半导体", "名称", "关联主题", "检索时间（北京时间）"]) assert.ok(html.includes(text));
  assert.match(html, /href="https:\/\/example.org\/policy"/);
  assert.doesNotMatch(html, /官方政策|确定受益|验证通过|已核验的政策/);
  const escaped = fixture(); escaped.data[0].excerpt = "<script>alert(1)</script>";
  assert.match(render({ data: escaped }), /&lt;script&gt;/);
  assert.doesNotMatch(render({ data: escaped }), /<script>/);
});

test("查询四态明确，局部故障仍显示结果，更多报道默认折叠但不丢弃", () => {
  assert.match(render({ pending: true }), /正在查找/);
  assert.match(render({ paused: true }), /当前离线/);
  assert.match(render({ failed: true, error: "HTTP 503" }), /HTTP 503/);
  assert.match(render({ data: { ...fixture(), status: "empty", data: [] } }), /暂无匹配内容/);
  for (const state of [{ failed: true }, { paused: true }]) {
    const html = render({ ...state, data: fixture() });
    assert.match(html, /保留上次同条件检索结果/);
    assert.match(html, /设备主题报道/);
  }
  const value = fixture();
  value.status = "partial";
  value.data = Array.from({ length: 7 }, (_, i) => ({ ...value.data[0], id: `report-${i}`, title: `更多报道 ${i}` }));
  const html = render({ data: value });
  assert.match(html, /部分资料源暂不可用/);
  assert.match(html, /展开其余 4 篇相关报道/);
  assert.match(html, /更多报道 6/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
});

test("默认先展示关联检索，旧证据与本金表单独立折叠且缺证据门禁保留", () => {
  const panel = compileView("../components/research/policy-capital-panel.tsx", {
    "@/lib/policy-capital": policyCapital,
    "./related-research-panel": { RelatedResearchPanel: () => createElement("section", { "aria-label": "相关政策与资讯" }, "关联资料入口") },
  }).PolicyCapitalPanel;
  const html = renderToStaticMarkup(createElement(panel, { kind: "stock", code: "688012", name: "中微公司" } as never));
  assert.ok(html.indexOf("关联资料入口") < html.indexOf("已核验证据与 AI 深入研究"));
  assert.match(html, /<summary[^>]*>本金执行约束 · 单笔限价买入<\/summary>/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>核验资金与缺项<\/button>/);
  assert.match(html, /需先取得当前标的证据包/);
  assert.doesNotMatch(html, />开始研究<|当前标的专属证据与约束/);
});

test("相关资料消费者把解读放在原文列表前，传入本查询快照并区分检索与AI生成", () => {
  const received: unknown[] = [];
  const data = fixture();
  const panel = compileView("../components/research/related-research-panel.tsx", {
    "@tanstack/react-query": { useQuery: () => ({ data, isPending: false, isFetching: false, isPaused: false, isError: false, refetch: () => {} }) },
    "@/lib/related-research": { fetchRelatedResearch, relatedResearchKey, relatedResearchQueryPolicy, relatedResearchRequest },
    "./related-interpretation-panel": { RelatedInterpretationPanel: (props: unknown) => { received.push(props); return createElement("section", null, "通俗解读入口"); } },
    "./related-research-content": { RelatedResearchContent: () => createElement("section", null, "原文列表") },
  }).RelatedResearchPanel;
  const html = renderToStaticMarkup(createElement(panel, { kind: request.kind, code: request.code, name: request.name } as never));
  assert.deepEqual(received, [{ request, current: data }]);
  assert.ok(html.indexOf("通俗解读入口") < html.indexOf("原文列表"));
  assert.match(html, /「刷新资料」和「搜索资料」只做检索，不调用 AI/);
  assert.match(html, /解读由下方按钮单独生成/);
});
