import test from "node:test";
import assert from "node:assert/strict";
import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { copyableRelatedInterpretation, generateRelatedInterpretation, parseRelatedInterpretation, readRelatedInterpretation, relatedInterpretationKey, relatedInterpretationQueryPolicy, relatedSnapshotChanged, type RelatedInterpretationResult } from "../lib/related-interpretation.ts";
import type { RelatedResearchRequest } from "../lib/related-research.ts";

const request: RelatedResearchRequest = { kind: "stock", code: "688648", name: "中邮科技", q: "" };
function fixture(): RelatedInterpretationResult {
  const inference = (text: string) => ({ text, basis: "inference" as const });
  return {
    schema_version: 1, subject_kind: "stock", subject_id: "688648", subject_name: "中邮科技", query: "",
    generated_at: "2026-10-27T12:00:00+08:00", model: "test", prompt_version: "v1", review_status: "ai_unreviewed", purpose: "related_material_context_only", status: "interpreted", snapshot_sha256: "a".repeat(64),
    snapshot: {
      schema_version: 1, subject_kind: "stock", subject_id: "688648", subject_name: "中邮科技", query: "", status: "ready",
      keywords: [{ term: "智能物流", origin: "business" }],
      data: [
        { id: "report-1", title: "物流设备更新报道", url: "https://example.org/report", publisher: "报道来源", published_at: "2026-10-26", excerpt: "企业讨论物流设备更新需求，具体订单尚未披露。", source: "news_archive", category: "report", relevance: "topic", matched_keywords: ["物流"], reason: "业务主题匹配" },
        { id: "policy-1", title: "产业政策档案", url: "https://example.org/policy", publisher: "政策档案", published_at: "2025-01-01", excerpt: "档案摘要记录历史政策目标，不代表执行结果。", source: "policy_archive", category: "policy", relevance: "topic", matched_keywords: ["设备"], reason: "设备主题匹配" },
      ], sources: [{ source: "news_archive", status: "ok", message: "" }, { source: "policy_archive", status: "ok", message: "" }], searched_at: "2026-10-27T11:59:00+08:00", window_days: 365, limitations: ["只取得标题与节选"],
    },
    analysis: {
      overview: "物流设备更新可能改变行业需求，仍需观察订单。",
      events: [{ title: "物流设备更新", source_ids: ["report-1"], summary: { text: "报道提到设备更新需求，尚未披露具体订单。", basis: "reported", quotes: [{ source_id: "report-1", field: "excerpt", quote: "具体订单尚未披露" }] }, impact_direction: "unclear",
        impact_path: inference("设备更新可能形成新增需求"), affected_scope: inference("涉及物流设备供应链"), duration: inference("持续时间取决于实际投资"), market_reaction: inference("情绪可能先变，未取得行情反馈"), business_realization: inference("订单到收入仍需交付"), subject_relation: inference("主营相关，尚无订单证据"), watchpoints: ["查看后续订单公告"] }],
      excluded_sources: [{ source_id: "policy-1", reason: "历史档案，当前相关性不足" }], limitations: ["产业影响属于条件性推断"],
    },
  };
}

test("解读按类型、代码、关键词隔离，显示名称更新不改变已存身份", () => {
  assert.equal(parseRelatedInterpretation(null, request), null);
  assert.equal(parseRelatedInterpretation(fixture(), request)?.analysis.events.length, 1);
  assert.equal(parseRelatedInterpretation(fixture(), { ...request, name: "最新显示名" })?.subject_name, "中邮科技");
  assert.deepEqual(relatedInterpretationKey(request), relatedInterpretationKey({ ...request, name: "最新显示名" }));
  for (const changed of [{ kind: "etf" as const }, { code: "600000" }, { q: "半导体" }]) {
    assert.notDeepEqual(relatedInterpretationKey(request), relatedInterpretationKey({ ...request, ...changed }));
    assert.throws(() => parseRelatedInterpretation(fixture(), { ...request, ...changed }));
  }
  const namedQuery = fixture(); namedQuery.query = "物流"; namedQuery.snapshot.query = "物流";
  assert.ok(parseRelatedInterpretation(namedQuery, { ...request, q: " 物流 " }));
});

test("快照身份、来源安全、时间与未复核标记必须有效", () => {
  for (const patch of [{ schema_version: 2 }, { review_status: "verified" }, { purpose: "buy_signal" }, { generated_at: "2026-10-27T12:00:00" }, { generated_at: "2026-02-30T12:00:00Z" }, { snapshot_sha256: "not-a-hash" }, { model: " " }, { extra: true }]) {
    assert.throws(() => parseRelatedInterpretation({ ...fixture(), ...patch }, request));
  }
  for (const patch of [{ subject_id: "600000" }, { subject_name: "另一个公司" }, { query: "设备" }]) {
    const value = fixture(); Object.assign(value.snapshot, patch);
    assert.throws(() => parseRelatedInterpretation(value, request));
  }
  for (const url of ["javascript:alert(1)", "data:text/html,test", "https://user:pass@example.org"]) {
    const value = fixture(); value.snapshot.data[0].url = url;
    assert.throws(() => parseRelatedInterpretation(value, request));
  }
});

test("每条资料只能归属一个事件或一个排除记录，不漏来源或重复归并", () => {
  const missing = fixture(); missing.analysis.excluded_sources = [];
  assert.throws(() => parseRelatedInterpretation(missing, request));
  const duplicate = fixture(); duplicate.analysis.events.push(duplicate.analysis.events[0]);
  assert.throws(() => parseRelatedInterpretation(duplicate, request));
  const overlap = fixture(); overlap.analysis.excluded_sources.push({ source_id: "report-1", reason: "重复排除" });
  assert.throws(() => parseRelatedInterpretation(overlap, request));
  const repeated = fixture(); repeated.analysis.events[0].source_ids.push("report-1");
  assert.throws(() => parseRelatedInterpretation(repeated, request));
  const unknown = fixture(); unknown.analysis.events[0].source_ids = ["missing"];
  assert.throws(() => parseRelatedInterpretation(unknown, request));
});

test("事实概况需真实连续引文，不能引用别的事件、补写条款或升级推断", () => {
  for (const patch of [{ quote: "政府已向该公司下达大额订单" }, { source_id: "policy-1" }, { field: "body" }, { quote: "具体订单披露" }, { quote: " " }]) {
    const value = fixture(); Object.assign(value.analysis.events[0].summary.quotes[0], patch);
    assert.throws(() => parseRelatedInterpretation(value, request));
  }
  const upgraded = fixture(); Object.assign(upgraded.analysis.events[0].impact_path, { basis: "reported" });
  assert.throws(() => parseRelatedInterpretation(upgraded, request));
  const noQuote = fixture(); noQuote.analysis.events[0].summary.quotes = [];
  assert.throws(() => parseRelatedInterpretation(noQuote, request));
  const titleOnly = fixture(); titleOnly.snapshot.data[0].excerpt = "";
  titleOnly.analysis.events[0].summary.quotes = [{ source_id: "report-1", field: "title", quote: "物流设备更新" }];
  assert.ok(parseRelatedInterpretation(titleOnly, request));
});

test("弱相关资料可全部排除，不能把无事件伪装成已有解读事件", () => {
  const value = fixture(); value.status = "no_relevant_events"; value.analysis.events = [];
  value.analysis.excluded_sources.push({ source_id: "report-1", reason: "只有主题提及" });
  assert.equal(parseRelatedInterpretation(value, request)?.analysis.events.length, 0);
  assert.throws(() => parseRelatedInterpretation({ ...value, status: "interpreted" }, request));
  assert.throws(() => parseRelatedInterpretation({ ...fixture(), status: "no_relevant_events" }, request));
});

test("资料刷新提示比较实际内容，单纯检索时间变新或顺序变化不误报", () => {
  const saved = fixture();
  assert.equal(relatedSnapshotChanged(saved), false);
  assert.equal(relatedSnapshotChanged(saved, { ...saved.snapshot, searched_at: "2026-10-27T13:00:00+08:00", data: [...saved.snapshot.data].reverse() }), false);
  const changed = structuredClone(saved.snapshot); changed.data[0].excerpt = "新增明确订单公告";
  assert.equal(relatedSnapshotChanged(saved, changed), true);
  assert.equal(relatedSnapshotChanged(saved, { ...saved.snapshot, data: [] }), true);
  assert.equal(relatedSnapshotChanged(saved, { ...saved.snapshot, query: "其他查询" }), true);
});

test("读取无生成，POST仅发送刷新标记，不接受前端文章或提示词", async () => {
  const original = globalThis.fetch;
  const calls: { url: string; method: string; body: unknown; signal: AbortSignal | null | undefined }[] = [];
  let response: unknown = null, status = 200;
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null, signal: init?.signal });
    return new Response(JSON.stringify(response), { status });
  };
  try {
    const controller = new AbortController();
    assert.equal(await readRelatedInterpretation(request, controller.signal), null);
    assert.equal(calls[0].signal, controller.signal);
    response = fixture();
    await generateRelatedInterpretation(request, false);
    await generateRelatedInterpretation(request, true);
    assert.deepEqual(calls.map(({ method, body }) => ({ method, body })), [
      { method: "GET", body: null }, { method: "POST", body: { refresh: false } }, { method: "POST", body: { refresh: true } },
    ]);
    const url = new URL(calls[0].url);
    assert.equal(url.pathname, "/api/research/related/interpretation");
    assert.equal(url.searchParams.get("code"), "688648");
    assert.equal(url.searchParams.get("kind"), "stock");
    response = { error: { code: "RELATED_INTERPRETATION_TIMEOUT", message: "本次生成超时，已保留原结果", retryable: true } }; status = 504;
    await assert.rejects(generateRelatedInterpretation(request, true), /本次生成超时/);
    assert.equal(calls.length, 4);
  } finally { globalThis.fetch = original; }
});

test("失败读取保留同键已存结果，换关键词不复用上一份解读", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
  let fail = false;
  const options = (q = "") => ({ queryKey: relatedInterpretationKey({ ...request, q }), ...relatedInterpretationQueryPolicy, queryFn: async () => { if (fail) throw new Error("读取失败"); return fixture(); } });
  try {
    const saved = await client.fetchQuery(options());
    const observer = new QueryObserver(client, options()); fail = true;
    const result = await observer.refetch();
    assert.equal(result.isError, true); assert.deepEqual(result.data, saved);
    observer.setOptions(options("半导体"));
    assert.equal(observer.getCurrentResult().data, undefined);
    observer.destroy();
  } finally { client.clear(); }
});

test("复制研究要点保留资料、推断和时间边界", () => {
  const value = fixture(); value.query = "物流"; value.snapshot.query = "物流";
  const text = copyableRelatedInterpretation(value);
  for (const expected of ["未经人工复核", "查询：物流", "资料快照检索", "资料概况", "产业怎样受影响（AI 推断）", "2026-10-26", "https://example.org/report", "后续核查", "资料限制"]) assert.ok(text.includes(expected));
});
