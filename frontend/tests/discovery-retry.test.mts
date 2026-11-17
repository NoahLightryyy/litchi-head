import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactElement } from "react";
import ts from "typescript";

const url = new URL("../components/shared/stock-discovery.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(url, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const require = createRequire(url);

function harness(query = "京泉华", keyword = query, fetching = false, failed = ["股票目录"]) {
  let refreshes = 0;
  const state = { data: { data: [], total: 0, failed_sources: failed }, isFetching: fetching,
    isLoading: false, isError: false, refetch: () => { refreshes++; } };
  const componentModule = { exports: {} as { StockDiscovery: (props: object) => ReactElement } };
  new Function("require", "module", "exports", compiled)((name: string) => {
    if (name === "react") return { useState: () => [query, () => {}], useMemo: (f: () => unknown) => f(), useSyncExternalStore: () => "[]" };
    if (name === "next/link") return { default: "a" };
    if (name === "@tanstack/react-query") return { useQuery: () => state };
    if (name === "@/lib/hooks/use-debounce") return { useDebounce: () => keyword };
    if (name === "@/lib/search-history") return { parseSearchHistory: () => [], searchHistorySnapshot: () => "[]", addSearchHistory: () => [], saveSearchHistory: () => {} };
    if (name === "@/lib/api/client" || name === "@/lib/discovery-search" || name.includes("discovery-rankings")) return {};
    return require(name);
  }, componentModule, componentModule.exports);
  const tree = componentModule.exports.StockDiscovery({});
  const form = (tree.props as { children: ReactElement[] }).children[0];
  return {
    submit: () => (form.props as { onSubmit: (event: object) => void }).onSubmit({ preventDefault() {} }),
    refreshes: () => refreshes,
    html: () => renderToStaticMarkup(tree),
  };
}

test("同一关键词再次点击搜索真正重新请求，不只是写历史", () => {
  const h = harness();
  h.submit();
  assert.equal(h.refreshes(), 1);
});

test("新关键词等待防抖、不重查旧词；请求中和空词不重复请求", () => {
  for (const h of [harness("新词", "旧词"), harness("京泉华", "京泉华", true), harness("", "")]) {
    h.submit();
    assert.equal(h.refreshes(), 0);
  }
});

test("目录失败时不将缺失数据说成没有这只股票，并提供重新搜索入口", () => {
  const html = harness().html();
  assert.match(html, /股票目录暂时没加载成功/);
  assert.match(html, /不能据此判断没有这只股票/);
  assert.match(html, /重新搜索/);
  assert.doesNotMatch(html, /未找到匹配结果/);
  assert.match(harness("不存在", "不存在", false, []).html(), /未找到匹配结果/);
});
