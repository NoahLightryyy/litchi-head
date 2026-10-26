import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as health from "../lib/backend-health.ts";

const componentUrl = new URL("../components/shared/backend-status.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(componentUrl, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
type Props = {
  degraded: boolean;
  diagnose: health.DiagnoseResult | null;
  message: string | null;
  t: (text: string) => string;
};
const componentModule = { exports: {} as { BackendDiagnosticsNotice: (props: Props) => unknown } };
const require = createRequire(componentUrl);
new Function("require", "module", "exports", compiled)((name: string) => {
  if (name === "@/lib/backend-health") return health;
  if (name === "./locale-provider") return {};
  return require(name);
}, componentModule, componentModule.exports);
const render = (props: Partial<Props> = {}) => renderToStaticMarkup(createElement(componentModule.exports.BackendDiagnosticsNotice, {
  degraded: true, diagnose: null, message: null, t: text => text, ...props,
}));

test("全局诊断默认折叠，只在摘要显示异常数量，展开保留所有检查事实", () => {
  const html = render({ diagnose: {
    status: "degraded",
    checks: {
      "kline:daily": { status: "warn", error: "数据源返回空数据" },
      valuation: { status: "warn", error: "数据源返回空数据" },
      news: { status: "fail", message: "刷新失败", error: "HTTP 502" },
      quotes: { status: "pass" },
    },
  } });
  assert.match(html, /<details\s/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:[=>\s])/);
  const summary = html.match(/<summary[^>]*>(.*?)<\/summary>/)?.[1] ?? "";
  assert.match(summary, /数据诊断 · 3 项异常/);
  assert.doesNotMatch(summary, /kline|valuation|502|刷新失败/);
  assert.match(html, /日 K 线 \(kline:daily\)：暂无数据/);
  assert.match(html, /估值数据 \(valuation\)：暂无数据/);
  assert.match(html, /新闻资讯 \(news\)：请求失败 · 刷新失败；HTTP 502/);
  assert.match(html, /实时行情 \(quotes\)：可用/);
});

test("诊断接口不可用与备用源失败分别说明，不谎报全服务正常", () => {
  const unavailable = render({ message: health.DIAGNOSTICS_UNAVAILABLE_MESSAGE });
  assert.match(unavailable, /数据诊断暂不可用/);
  assert.match(unavailable, /后端已连接，诊断信息暂不可用/);
  assert.doesNotMatch(unavailable, /0 项异常|全部正常/);
  const redundant = render({ degraded: false, diagnose: {
    status: "healthy_with_warnings",
    checks: {
      "market_index:eastmoney": { status: "fail", error: "timeout" },
      "market_index:sina": { status: "pass" },
    },
  } });
  assert.match(redundant, /备用来源暂不可用/);
  assert.match(redundant, /指数 · 东方财富 \(market_index:eastmoney\)：请求失败 · timeout/);
  assert.match(redundant, /指数 · 新浪 \(market_index:sina\)：可用/);
  assert.doesNotMatch(redundant, /部分异常/);
  assert.equal(render({ degraded: false, diagnose: { status: "healthy", checks: {} } }), "");
});

test("未知数据服务和诊断文本仍可查阅，并作为普通文本呈现", () => {
  const html = render({ diagnose: {
    status: "degraded",
    checks: { "unknown:source": { status: "fail", error: "<script>alert(1)</script>" } },
  } });
  assert.match(html, /unknown:source：请求失败/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
