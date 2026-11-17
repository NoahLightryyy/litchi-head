import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement, type ComponentType } from "react";
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as companies from "../lib/chain-companies.ts";
import type { ChainDraft } from "../lib/chain-draft.ts";

const draft: ChainDraft = { schema_version: 1, sector_code: "BK1184", sector_name: "人形机器人", generated_at: "2026-10-26T08:00:00Z", model: "test", cached: true, review_status: "ai_inferred_unverified", graph: { map_kind: "industry_chain", scope: "研究草图", nodes: [{ id: "parts", label: "零部件", role: "精密传动", verify: "业务资料" }, { id: "body", label: "整机", role: "整机生产", verify: "产品资料" }], edges: [{ source: "parts", target: "body", explanation: "投入" }] } };
function fixture(): companies.ChainCompanies {
  return { schema_version: 1, sector_code: draft.sector_code, sector_name: draft.sector_name, graph_revision: "a".repeat(64), graph_nodes: draft.graph.nodes.map(({ id, label }) => ({ id, label })), generated_at: "2026-10-26T10:00:00Z", model: "test", cached: false, review_status: "ai_unreviewed", companies: [
    { node_id: "parts", name: "绿的谐波", business: "精密传动产品", influence: "关注减速器技术与量产能力。", a_share_code: "688017", reference_status: "public_reference", sources: [{ title: "官方产品资料", url: "https://example.com/product", excerpt: "谐波减速器产品。", accessed_at: "2026-10-26T09:00:00Z" }] },
    { node_id: "body", name: "海外整机企业", business: "人形机器人整机", influence: "关注产品落地进展。", a_share_code: null, reference_status: "ai_candidate", sources: [] },
  ] };
}

test("企业消费者校验板块、节点、重复代码与来源", () => {
  assert.equal(companies.parseChainCompanies(fixture(), draft).companies.length, 2);
  for (const mutate of [
    (r: companies.ChainCompanies) => { r.sector_code = "BK0917"; },
    (r: companies.ChainCompanies) => { r.sector_name = "医疗器械"; },
    (r: companies.ChainCompanies) => { r.graph_nodes[0].label = "不同节点"; },
    (r: companies.ChainCompanies) => { r.companies[0].node_id = "missing"; },
    (r: companies.ChainCompanies) => { r.companies[1] = structuredClone(r.companies[0]); },
    (r: companies.ChainCompanies) => { r.companies[0].sources = []; },
    (r: companies.ChainCompanies) => { r.companies[0].sources[0].url = "javascript:alert(1)"; },
    (r: companies.ChainCompanies) => { r.companies[0].sources[0].url = "https://user:password@example.com"; },
    (r: companies.ChainCompanies) => { r.generated_at = "not a date"; },
  ]) { const data = fixture(); mutate(data); assert.throws(() => companies.parseChainCompanies(data, draft)); }
  const other = structuredClone(draft); other.graph.nodes[0].role = "其他作用";
  assert.notDeepEqual(companies.chainCompaniesKey(other), companies.chainCompaniesKey(draft));
});

const url = new URL("../components/sector/chain-companies.tsx", import.meta.url);
function compile(overrides: Record<string, unknown> = {}) {
  const mod = { exports: {} as Record<string, unknown> }, require = createRequire(url);
  new Function("require", "module", "exports", ts.transpileModule(readFileSync(url, "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText)((name: string) => name in overrides ? overrides[name] : name === "@/lib/chain-companies" ? companies : name === "@/lib/api/client" ? {} : name === "next/link" ? { default: (props: { href: string; children: unknown }) => createElement("a", { href: props.href }, props.children as never) } : require(name), mod, mod.exports);
  return mod.exports;
}
interface Props { draft: ChainDraft; data?: companies.ChainCompanies; loading: boolean; offline: boolean; error: string | null; onRetry: () => void }
const Content = compile().ChainCompaniesContent as ComponentType<Props>;
const render = (values: Partial<Props> = {}) => renderToStaticMarkup(createElement(Content, { draft, loading: false, offline: false, error: null, onRetry: () => {}, ...values }));

test("各环节展示企业业务和关注理由，只有已核对A股代码可进股票页", () => {
  const html = render({ data: fixture() });
  assert.match(html, /零部件代表企业/); assert.match(html, /整机代表企业/);
  assert.match(html, /href="\/stock\/688017"/); assert.match(html, /为何关注/);
  assert.match(html, /海外整机企业/); assert.match(html, /AI 候选 · 业务资料待补充/);
  assert.equal((html.match(/href="\/stock\//g) ?? []).length, 1);
  assert.match(html, /读取于 2026\/10\/26 17:00:00/);
  assert.match(html, /不代表发布日期/); assert.match(html, /不是市占率排名/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
});

test("生成中、离线和失败分别提示，已有清单时间与来源保留且原文转义", () => {
  assert.match(render({ loading: true }), /正在整理代表企业/);
  assert.match(render({ offline: true }), /当前离线/);
  const failed = render({ data: fixture(), error: "整理超时" });
  assert.match(failed, /保留上次成功清单与原时间/); assert.match(failed, /绿的谐波/);
  assert.match(failed, /2026\/10\/26 18:00:00/);
  const data = fixture(); data.companies[0].business = "<script>evil()</script>";
  assert.doesNotMatch(render({ data }), /<script>/); assert.match(render({ data }), /&lt;script&gt;/);
});

test("首次补充读缓存、更新才强制生成，失败不自动重试，取消旧请求后写入", async () => {
  let options: Record<string, unknown> = {}, mutation: Record<string, unknown> = {};
  const requests: unknown[] = [], events: string[] = [];
  const Panel = compile({
    "@/lib/api/client": { api: { postRaw: async (_path: string, body: unknown) => { requests.push(body); return fixture(); } } },
    "@tanstack/react-query": {
      useQueryClient: () => ({ cancelQueries: async () => { events.push("cancel"); }, setQueryData: () => events.push("write") }),
      useQuery: (value: Record<string, unknown>) => { options = value; return { data: fixture(), isFetching: false }; },
      useMutation: (value: Record<string, unknown>) => { mutation = value; return { isPending: false }; },
    },
  }).ChainCompaniesPanel as (props: { draft: ChainDraft }) => unknown;
  const old = Object.getOwnPropertyDescriptor(navigator, "onLine");
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  try {
    Panel({ draft }); assert.equal(options.retry, false); assert.equal(options.refetchOnWindowFocus, false);
    await (options.queryFn as () => Promise<unknown>)();
    await (mutation.mutationFn as () => Promise<unknown>)();
    assert.deepEqual(requests, [{ sector_name: "人形机器人", refresh: false }, { sector_name: "人形机器人", refresh: true }]);
    await (mutation.onSuccess as (value: unknown) => Promise<void>)(fixture());
    assert.deepEqual(events, ["cancel", "write"]);
  } finally { if (old) Object.defineProperty(navigator, "onLine", old); else Reflect.deleteProperty(navigator, "onLine"); }
});

test("首次网络失败重试先读已完成的缓存，只有更新或缓存损坏才重新生成", async () => {
  const events: string[] = [];
  let state: { data?: companies.ChainCompanies; error?: unknown } = {};
  let mutation: Record<string, unknown> = {};
  const Panel = compile({
    "@tanstack/react-query": {
      useQueryClient: () => ({ cancelQueries: async () => { throw new Error("cancel failed"); }, setQueryData: () => events.push("write") }),
      useQuery: () => ({ ...state, isFetching: false, refetch: () => events.push("read") }),
      useMutation: (value: Record<string, unknown>) => { mutation = value; return { isPending: false, mutate: () => events.push("generate") }; },
    },
  }).ChainCompaniesPanel as (props: { draft: ChainDraft }) => ReactElement<Props>;
  state = { error: new Error("network timeout") };
  Panel({ draft }).props.onRetry();
  state = { error: { code: "CHAIN_COMPANIES_STORAGE" } };
  Panel({ draft }).props.onRetry();
  state = { data: fixture() };
  Panel({ draft }).props.onRetry();
  assert.deepEqual(events, ["read", "generate", "generate"]);
  const warn = console.warn;
  console.warn = () => {};
  try { await (mutation.onSuccess as (value: unknown) => Promise<void>)(fixture()); }
  finally { console.warn = warn; }
  assert.equal(events.at(-1), "write");
});
