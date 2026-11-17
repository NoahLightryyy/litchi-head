import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { api } from "../lib/api/client.ts";
import * as observation from "../lib/retro-observations.ts";

const record = { record_id: "retro_a", stock_code: "300916", stock_name: "朗特智能", created_at: "2026-10-07T12:00:00", confidence: .6, weighted_score: 60, consensus: "Bullish" };
const item = { record_id: "retro_a", stock_code: "300916", status: "observed", message: "按已取得的收盘日期比较。", recorded_date: "2026-10-07", baseline_date: "2026-10-07", latest_date: "2026-10-26", baseline_price: 10, latest_price: 11, change_pct: 10, alignment: "same", source: "tencent", price_basis: "raw", baseline_method: "first_available_close_on_or_after_record_date", fetched_at: "2026-10-27T06:00:00+08:00" };
test("消费者核对身份、区间及价格算术，不接受错股/重复/不合理涨幅", async () => {
  const old = api.get;
  try {
    api.get = async () => [item] as never;
    assert.equal((await observation.readRetroObservations([record], new AbortController().signal))[0].change_pct, 10);
    for (const replacement of [{ ...item, stock_code: "000001" }, { ...item, change_pct: 99 }, { ...item, latest_date: item.baseline_date }]) {
      api.get = async () => [replacement] as never;
      await assert.rejects(observation.readRetroObservations([record], new AbortController().signal));
    }
    api.get = async () => [item, item] as never;
    await assert.rejects(observation.readRetroObservations([record, { ...record, record_id: "b" }], new AbortController().signal));
  } finally { api.get = old; }
});
let capturedQuery: Record<string, unknown> = {};
const component = new URL("../components/retro/retro-board.tsx", import.meta.url);
// Dynamic transpilation harness inspects React element props for actual event behavior.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const loaded = { exports: {} as Record<string, (props: any) => any> };
new Function("require", "module", "exports", ts.transpileModule(readFileSync(component, "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)((id: string) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  if (id === "next/link") return { default: (props: any) => createElement("a", props) };
  if (id === "@/lib/retro-observations") return observation;
  if (id === "@tanstack/react-query") return { useQuery: (options: Record<string, unknown>) => { capturedQuery = options; return { data: [item] }; } };
  if (id === "@/lib/hooks/use-retro") return { useRetroRecords: () => ({ data: Array.from({length: 14}, (_, i) => ({ ...record, record_id: `r${i}` })) }), useRetroSummary: () => ({ data: { total_records: 14, today_records: 1 } }), useDeleteRecord: () => ({ mutate: () => {} }) };
  return createRequire(component)(id);
}, loaded, loaded.exports);
test("复盘自动读取本页10条，不再要求人工判定；下一页可用", () => {
  const html = renderToStaticMarkup(createElement(loaded.exports.RetroBoard));
  assert.equal((html.match(/href="\/stock\/300916"/g) ?? []).length, 10);
  assert.match(html, /第 1 \/ 2 页/); assert.match(html, /不用你填写结果/);
  assert.equal(capturedQuery.refetchInterval, 60000); assert.equal(capturedQuery.retry, false);
  assert.doesNotMatch(html, /待标记结果|待判定/);
});
test("名称与代码都是详情链接；点击不会同时展开行；行情带实际日期", () => {
  const row = loaded.exports.RetroRow({ record, observation: item, expanded: false, onToggle: () => assert.fail("must not toggle"), onDelete: () => {} });
  const link = row.props.children[0].props.children[1].props.children;
  assert.equal(link.props.href, "/stock/300916");
  let stopped = false; link.props.onClick({ stopPropagation: () => { stopped = true; } }); assert.equal(stopped, true);
  const html = renderToStaticMarkup(row);
  assert.match(html, /10.00%/); assert.match(html, /2026-10-07/); assert.match(html, /目前与判断同向/);
  assert.doesNotMatch(html, /正确|收益/);
});
