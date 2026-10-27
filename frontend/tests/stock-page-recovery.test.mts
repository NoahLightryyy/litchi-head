import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement, type ReactElement } from "react";
import ts from "typescript";
import * as recovery from "../lib/intraday-recovery.ts";
import * as identity from "../lib/stock-identity.ts";

function compile(file: string, mocks: Record<string, unknown>) {
  const url = new URL(file, import.meta.url);
  const require = createRequire(url);
  const compiled = ts.transpileModule(readFileSync(url, "utf8"), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  }}).outputText;
  const compiledModule = { exports: {} as Record<string, unknown> };
  new Function("require", "module", "exports", compiled)((name: string) => name in mocks ? mocks[name] : require(name), compiledModule, compiledModule.exports);
  return compiledModule.exports;
}

function page(quote: object | null, failed = false, named = true, fetching = false) {
  let refreshes = 0;
  const mocks: Record<string, unknown> = {
    "next/navigation": { useParams: () => ({ code: "002885" }) },
    "next/link": { default: "a" },
    "@/components/shared/locale-provider": { useLocale: () => ({ t: (v: string) => v }) },
    "@/lib/hooks/use-stock": {
      useStockQuote: () => ({ data: quote, isError: failed, isLoading: false, isFetching: fetching,
        refetch: () => { refreshes++; } }),
      useStockIdentity: () => ({ data: named ? { code: "002885", name: "京泉华" } : null }),
    },
    "@/lib/hooks/use-debate": { useTrustLeaderboard: () => ({ data: [], isLoading: false }) },
    "@/lib/stock-identity": identity,
    "@/lib/intraday-recovery": recovery,
  };
  for (const [file, symbol] of [
    ["research/research-context", "ResearchContext"], ["stock/quote-card", "QuoteCard"],
    ["stock/watch-button", "WatchButton"], ["stock/company-research-panel", "CompanyResearchPanel"],
    ["stock/debate-panel", "DebatePanel"], ["stock/news-feed", "NewsFeed"],
    ["stock/capital-flow-panel", "CapitalFlowPanel"], ["stock/technical-indicators-panel", "TechnicalIndicatorsPanel"],
    ["stock/financial-panel", "FinancialPanel"], ["stock/trust-chart", "TrustChart"],
    ["stock/intraday-battlefield-panel", "IntradayBattlefieldPanel"],
  ]) mocks[`@/components/${file}`] = { [symbol]: (p: { name?: string; stockName?: string; quote?: { name: string } }) =>
    createElement("div", { "data-child": symbol }, p.name ?? p.stockName ?? p.quote?.name) };
  const Component = compile("../app/stock/[code]/page.tsx", mocks).default as () => ReactElement;
  return { html: renderToStaticMarkup(createElement(Component)), refreshes: () => refreshes };
}

test("missing quote keeps the known company name in header, watchlist, research and debate", () => {
  const html = page(null).html;
  assert.match(html, /京泉华/);
  for (const child of ["WatchButton", "ResearchContext", "DebatePanel"]) assert.match(html, new RegExp(`${child}[^>]*>京泉华`));
  assert.match(html, /报价暂未取得/);
  assert.doesNotMatch(html, /个股名称与报价尚未取得/);
  assert.match(html, /重新获取报价/);
});

test("refresh failure keeps last successful same-code quote with a visible warning", () => {
  const html = page({ code: "002885", name: "京泉华" }, true).html;
  assert.match(html, /QuoteCard/);
  assert.match(html, /刷新未成功/);
  assert.match(html, /上次报价/);
  assert.doesNotMatch(html, /报价暂未取得/);
});

test("unknown identity or previous-code quote never names the wrong stock", () => {
  const html = page({ code: "300750", name: "宁德时代" }, false, false).html;
  assert.doesNotMatch(html, /宁德时代/);
  assert.doesNotMatch(html, /QuoteCard/);
  assert.match(html, /002885/);
  assert.match(html, /报价暂未取得/);
});

test("identity hook uses existing stock-only search; a null quote is a retryable error, not cached success", async () => {
  let current: unknown = null;
  const hooks = compile("../lib/hooks/use-stock.ts", {
    "@tanstack/react-query": { useQuery: (options: unknown) => options },
    "@/lib/api/stocks": { searchStocks: async () => [{ code: "002885", name: "京泉华" }], fetchQuote: async () => current },
    "@/lib/stock-identity": identity,
    "@/lib/intraday-recovery": recovery,
    "./use-debounce": { useDebounce: (value: string) => value },
  }) as { useStockIdentity: (code: string) => { queryFn: () => Promise<unknown>; enabled: boolean };
    useStockQuote: (code: string) => { queryFn: () => Promise<unknown>; retry: boolean } };
  assert.deepEqual(await hooks.useStockIdentity("002885").queryFn(), { code: "002885", name: "京泉华" });
  assert.equal(hooks.useStockIdentity("abc").enabled, false);
  const quote = hooks.useStockQuote("002885");
  assert.equal(quote.retry, false);
  await assert.rejects(quote.queryFn());
  current = { code: "002885", name: "京泉华" };
  assert.equal(await quote.queryFn(), current);
});
