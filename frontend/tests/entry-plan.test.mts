import test from "node:test";
import assert from "node:assert/strict";
import { generateEntryPlan, parseEntryPlan, readEntryPlan, type EntryPlanResult } from "../lib/entry-plan.ts";

const identity = { sessionId: "session-1", stockCode: "688648", instrumentType: "stock" as const };
function fixture(): EntryPlanResult {
  return {
    schema_version: 1, session_id: "session-1", source_session_id: "session-1", stock_code: "688648", instrument_type: "stock", stock_name: "中邮科技",
    source_research_generated_at: "2026-10-26T15:30:00+08:00", generated_at: "2026-10-27T09:00:00+08:00", model: "test-model",
    purpose: "conditional_research_plan", status_basis: "ai_review_of_dated_evidence", cached: false, gaps: [],
    evidence: [
      { id: "analysis-1", kind: "analysis", title: "本股辩论", data_time: "2026-10-26 15:30", content: "研究观点" },
      { id: "quote-1", kind: "quote", title: "本股行情", data_time: "2026-10-26 15:00", content: "价格10元" },
    ],
    plans: (["short", "medium", "long"] as const).map((horizon) => ({
      horizon, status: "waiting", summary: "等待趋势确认后观察",
      conditions: [{ condition: "放量站稳关键位", status: "unmet", explanation: "尚未站稳", evidence_ids: ["quote-1"] }],
      entry_low: 10, entry_high: 11, stop_loss: 9, price_basis: "前期支撑附近", price_evidence_ids: ["quote-1"],
      invalidation: ["跌破支撑"], batches: [{ budget_pct: 30, trigger: "首次站稳" }, { budget_pct: 70, trigger: "回踩后再确认" }],
      position_note: "按用户资金约束计算", limitations: ["尚未持续监测"],
    })),
  };
}

test("股票与ETF按会话及标的身份严格隔离", () => {
  assert.equal(parseEntryPlan(fixture(), identity).plans.length, 3);
  for (const patch of [
    { schema_version: 2 }, { session_id: "other" }, { source_session_id: "other" }, { stock_code: "600000" },
    { instrument_type: "etf" }, { purpose: "trade_order" }, { status_basis: "live_monitor" }, { cached: "false" }, { extra: "value" },
  ]) assert.throws(() => parseEntryPlan({ ...fixture(), ...patch }, identity));
  const etf = { ...fixture(), stock_code: "560780", instrument_type: "etf" };
  assert.equal(parseEntryPlan(etf, { sessionId: "session-1", stockCode: "560780", instrumentType: "etf" }).instrument_type, "etf");
  for (const bad of [null, [], "data", { data: fixture() }]) assert.throws(() => parseEntryPlan(bad, identity));
});

test("来源时间与完整三个周期不能缺失或重复", () => {
  for (const generated_at of ["invalid", "2026-02-30T09:00:00+08:00", "2026-10-27T09:00:00", null]) {
    assert.throws(() => parseEntryPlan({ ...fixture(), generated_at }, identity));
  }
  const value = fixture();
  for (const plans of [[], value.plans.slice(1), [value.plans[0], value.plans[0], value.plans[2]], [...value.plans, value.plans[0]]]) {
    assert.throws(() => parseEntryPlan({ ...value, plans }, identity));
  }
});

test("拒绝未知、重复引用，以及只引用旧AI观点的候选价格", () => {
  for (const ids of [["missing"], ["quote-1", "quote-1"], []]) {
    const value = fixture(); value.plans[0].conditions[0].evidence_ids = ids;
    assert.throws(() => parseEntryPlan(value, identity));
  }
  for (const ids of [["missing"], ["analysis-1"], []]) {
    const value = fixture(); value.plans[0].price_evidence_ids = ids;
    assert.throws(() => parseEntryPlan(value, identity));
  }
  const duplicate = fixture(); duplicate.evidence.push(duplicate.evidence[0]);
  assert.throws(() => parseEntryPlan(duplicate, identity));
});

test("引用历史AI的条件即使同时引用行情也不能标为已满足或未满足", () => {
  for (const status of ["met", "unmet"] as const) {
    const value = fixture();
    value.plans[0].conditions[0].status = status;
    value.plans[0].conditions[0].evidence_ids = ["analysis-1"];
    assert.throws(() => parseEntryPlan(value, identity));
    value.plans[0].conditions[0].evidence_ids.push("quote-1");
    assert.throws(() => parseEntryPlan(value, identity));
    value.plans[0].conditions[0].evidence_ids = ["quote-1"];
    assert.equal(parseEntryPlan(value, identity).plans[0].conditions[0].status, status);
  }
  const unknown = fixture();
  unknown.plans[0].conditions[0].status = "unknown";
  unknown.plans[0].conditions[0].evidence_ids = ["analysis-1"];
  assert.equal(parseEntryPlan(unknown, identity).plans[0].conditions[0].status, "unknown");
});

test("候选价格须同时有值，止损更低；非有限数和无条件的consider被拒绝", () => {
  for (const patch of [
    { stop_loss: null }, { entry_low: null }, { entry_high: Infinity }, { stop_loss: NaN }, { stop_loss: 10 },
    { stop_loss: 0 }, { entry_low: 12 }, { entry_low: "10" }, { status: "consider" },
  ]) {
    const value = fixture(); Object.assign(value.plans[0], patch);
    assert.throws(() => parseEntryPlan(value, identity));
  }
  const met = fixture(); met.plans[0].status = "consider"; met.plans[0].conditions[0].status = "met";
  assert.equal(parseEntryPlan(met, identity).plans[0].status, "consider");
  const unavailable = fixture(); Object.assign(unavailable.plans[0], { entry_low: null, entry_high: null, stop_loss: null, price_evidence_ids: [] });
  assert.equal(parseEntryPlan(unavailable, identity).plans[0].entry_low, null);
});

test("分批预算必须合计100%，未知条件状态与额外模型字段被拒绝", () => {
  for (const budget_pct of [-1, 0, 31, Infinity, NaN, "30"]) {
    const value = fixture(); Object.assign(value.plans[0].batches[0], { budget_pct });
    assert.throws(() => parseEntryPlan(value, identity));
  }
  const invalidStatus = fixture(); Object.assign(invalidStatus.plans[0].conditions[0], { status: "ready_to_buy" });
  assert.throws(() => parseEntryPlan(invalidStatus, identity));
  const extra = fixture(); Object.assign(extra.plans[0], { position_pct: 80 });
  assert.throws(() => parseEntryPlan(extra, identity));
  const blank = fixture(); blank.plans[0].invalidation = [" "];
  assert.throws(() => parseEntryPlan(blank, identity));
});

test("分批比例最多两位小数，与后端和本地金额试算精度一致", () => {
  const value = fixture();
  value.plans[0].batches[0].budget_pct = 33.333;
  value.plans[0].batches[1].budget_pct = 66.667;
  assert.throws(() => parseEntryPlan(value, identity));
  value.plans[0].batches[0].budget_pct = 0.01;
  value.plans[0].batches[1].budget_pct = 99.99;
  assert.equal(parseEntryPlan(value, identity).plans[0].batches[0].budget_pct, 0.01);
});

test("读取不触发生成，生成只传refresh且不自动重试失败", async () => {
  const original = globalThis.fetch;
  const requests: { url: string; method: string; body: unknown }[] = [];
  let response: unknown = null;
  let status = 200;
  globalThis.fetch = async (url, init) => {
    requests.push({ url: String(url), method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
    return new Response(JSON.stringify(response), { status, headers: { "content-type": "application/json" } });
  };
  try {
    assert.equal(await readEntryPlan(identity), null);
    response = fixture();
    assert.equal((await generateEntryPlan(identity, false)).stock_code, identity.stockCode);
    await generateEntryPlan(identity, true);
    assert.deepEqual(requests.map(({ method, body }) => ({ method, body })), [
      { method: "GET", body: null }, { method: "POST", body: { refresh: false } }, { method: "POST", body: { refresh: true } },
    ]);
    assert.ok(requests.every(({ url }) => url.endsWith("/debate/session-1/entry-plan")));
    response = { error: { code: "ENTRY_PLAN_TIMEOUT", message: "本次计划生成超时", retryable: true } }; status = 504;
    await assert.rejects(generateEntryPlan(identity, true), /本次计划生成超时/);
    assert.equal(requests.length, 4);
  } finally { globalThis.fetch = original; }
});
