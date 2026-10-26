import test from "node:test";
import assert from "node:assert/strict";
import { sizeEntryPlan, type EntryPlanSizingInput } from "../lib/entry-plan-sizing.ts";

const input = (): EntryPlanSizingInput => ({
  totalAssetsCny: "100000", cashAvailableCny: "30000", instrumentLimitCny: "20000",
  currentHoldingCny: "5000", newRiskBudgetCny: "500", entryPriceCny: "10",
  stopPriceCny: "9", batchPercentages: ["30", "30", "40"],
});

test("新增仓位同时受风险、现金和现有持仓后的额度限制", () => {
  const result = sizeEntryPlan(input());
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.equal(result.additionalAmountCny, "5000.00");
  assert.equal(result.capitalCapacityCny, "15000.00");
  assert.equal(result.riskCapacityCny, "5000.00");
  assert.equal(result.additionalPositionPct, "5.00");
  assert.equal(result.totalPositionPct, "10.00");
  assert.equal(result.plannedNewLossCny, "500.00");
  assert.deepEqual(result.batches.map((batch) => batch.amountCny), ["1500.00", "1500.00", "2000.00"]);
  assert.ok(result.notes.some((note) => note.includes("现有持仓")));
  assert.equal("quantity" in result, false);

  const cashLimited = sizeEntryPlan({ ...input(), cashAvailableCny: "1000" });
  assert.equal(cashLimited.status === "ready" && cashLimited.additionalAmountCny, "1000.00");
  const capLimited = sizeEntryPlan({ ...input(), instrumentLimitCny: "6000" });
  assert.equal(capLimited.status === "ready" && capLimited.additionalAmountCny, "1000.00");
});

test("所有资金和价格必须显式填写，缺项不返回伪零结果", () => {
  for (const field of ["totalAssetsCny", "cashAvailableCny", "instrumentLimitCny", "currentHoldingCny", "newRiskBudgetCny", "entryPriceCny", "stopPriceCny"] as const) {
    const result = sizeEntryPlan({ ...input(), [field]: " " });
    assert.equal(result.status, "incomplete", field);
    assert.equal("additionalAmountCny" in result, false);
    if (result.status !== "ready") assert.ok(result.issues.some((issue) => issue.field === field));
  }
});

test("拒绝负数、非十进制数、超过支持精度以及无效止损价格", () => {
  for (const value of ["-1", "NaN", "Infinity", "1e3", "1,000", "1.001", "9".repeat(19)]) {
    const result = sizeEntryPlan({ ...input(), cashAvailableCny: value });
    assert.equal(result.status, "invalid", value);
    assert.equal("additionalAmountCny" in result, false);
  }
  for (const stopPriceCny of ["0", "10", "11", "0.0000001"]) {
    assert.equal(sizeEntryPlan({ ...input(), stopPriceCny }).status, "invalid");
  }
  for (const entryPriceCny of ["0", "-1"]) {
    assert.equal(sizeEntryPlan({ ...input(), entryPriceCny }).status, "invalid");
  }
});

test("拒绝账户资金、持仓与标的上限之间的矛盾", () => {
  for (const patch of [
    { totalAssetsCny: "0" }, { cashAvailableCny: "100001" },
    { currentHoldingCny: "100001", instrumentLimitCny: "100001" },
    { cashAvailableCny: "96000" }, { instrumentLimitCny: "100001" },
    { currentHoldingCny: "20001" }, { newRiskBudgetCny: "100001" },
  ]) {
    assert.equal(sizeEntryPlan({ ...input(), ...patch }).status, "invalid", JSON.stringify(patch));
  }
});

test("已满仓位额度、零现金或零新增风险预算明确说明无可新增额度", () => {
  for (const patch of [
    { currentHoldingCny: "20000" }, { cashAvailableCny: "0" }, { newRiskBudgetCny: "0" },
  ]) {
    const result = sizeEntryPlan({ ...input(), ...patch });
    assert.equal(result.status, "no_capacity");
    assert.equal("additionalAmountCny" in result, false);
    if (result.status !== "ready") assert.ok(result.issues.length > 0);
  }
});

test("分批比例需为正且精确合计100%，不隐式归一化", () => {
  for (const batchPercentages of [["50", "40"], ["50", "60"], ["0", "100"], ["-1", "101"], ["0.001", "99.999"], ["50", ""], ["NaN", "100"], Array(21).fill("1")]) {
    const result = sizeEntryPlan({ ...input(), batchPercentages });
    assert.notEqual(result.status, "ready", batchPercentages.join("/"));
    assert.equal("batches" in result, false);
  }
  assert.equal(sizeEntryPlan({ ...input(), batchPercentages: [] }).status, "incomplete");
});

test("金额使用整数分运算，风险上限向下取整，分批尾差守恒", () => {
  const result = sizeEntryPlan({ ...input(), newRiskBudgetCny: "0.01", entryPriceCny: "0.749", stopPriceCny: "0.7", batchPercentages: ["33.33", "33.33", "33.34"] });
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.equal(result.additionalAmountCny, "0.15");
  assert.equal(result.plannedNewLossCny, "0.01");
  assert.deepEqual(result.batches.map((batch) => batch.amountCny), ["0.05", "0.05", "0.05"]);

  const cent = sizeEntryPlan({ ...input(), cashAvailableCny: "0.01", batchPercentages: ["33.33", "33.33", "33.34"] });
  assert.equal(cent.status, "ready");
  if (cent.status === "ready") assert.deepEqual(cent.batches.map((batch) => batch.amountCny), ["0.00", "0.00", "0.01"]);
});

test("大额、微小价差与批次拆分仍然精确，不依赖Number安全整数", () => {
  const result = sizeEntryPlan({ totalAssetsCny: "999999999999999999.99", cashAvailableCny: "999999999999999999.99", instrumentLimitCny: "999999999999999999.99", currentHoldingCny: "0", newRiskBudgetCny: "999999999999999999.99", entryPriceCny: "1.000001", stopPriceCny: "1", batchPercentages: ["50", "50"] });
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.equal(result.additionalAmountCny, "999999999999999999.99");
  assert.deepEqual(result.batches.map((batch) => batch.amountCny), ["500000000000000000.00", "499999999999999999.99"]);
  assert.equal(result.additionalPositionPct, "100.00");
});

test("逐分检查小额分批：总额守恒且计划亏损不超过新增风险预算", () => {
  const cents = (value: string) => BigInt(value.replace(".", ""));
  for (let count = 1; count <= 101; count++) {
    const cash = `${Math.floor(count / 100)}.${String(count % 100).padStart(2, "0")}`;
    const result = sizeEntryPlan({ ...input(), cashAvailableCny: cash, newRiskBudgetCny: "0.01", entryPriceCny: "0.749", stopPriceCny: "0.711", batchPercentages: ["12.34", "23.45", "64.21"] });
    assert.equal(result.status, "ready");
    if (result.status !== "ready") continue;
    const amount = cents(result.additionalAmountCny);
    assert.equal(result.batches.reduce((sum, batch) => sum + cents(batch.amountCny), 0n), amount);
    assert.ok(amount <= BigInt(count));
    assert.ok(cents(result.plannedNewLossCny) <= 1n);
  }
});
