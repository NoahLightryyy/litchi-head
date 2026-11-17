/** Local amount-only scenario. No account inputs are sent to an AI or broker. */
export interface EntryPlanSizingInput {
  totalAssetsCny: string;
  cashAvailableCny: string;
  instrumentLimitCny: string;
  currentHoldingCny: string;
  newRiskBudgetCny: string;
  entryPriceCny: string;
  stopPriceCny: string;
  batchPercentages: readonly string[];
}

export interface EntryPlanSizingIssue {
  field: string;
  code: "missing" | "invalid_number" | "precision" | "non_positive" | "inconsistent" | "no_capacity";
  message: string;
}

export type EntryPlanSizingResult = {
  status: "ready";
  additionalAmountCny: string;
  capitalCapacityCny: string;
  riskCapacityCny: string;
  additionalPositionPct: string;
  totalPositionPct: string;
  plannedNewLossCny: string;
  batches: { percentage: string; amountCny: string }[];
  notes: string[];
} | {
  status: "incomplete" | "invalid" | "no_capacity";
  issues: EntryPlanSizingIssue[];
};

const MONEY_FIELDS = {
  totalAssetsCny: "账户总资产",
  cashAvailableCny: "可用现金",
  instrumentLimitCny: "该标的总投入上限",
  currentHoldingCny: "该标的现有持仓市值",
  newRiskBudgetCny: "此次新增可承受亏损金额",
} as const;

function fixed(value: bigint, places = 2): string {
  const digits = value.toString().padStart(places + 1, "0");
  return `${digits.slice(0, -places)}.${digits.slice(-places)}`;
}

function parseFixed(
  raw: unknown, field: string, label: string, places: number, issues: EntryPlanSizingIssue[],
): bigint | null {
  if (raw === undefined || raw === null || typeof raw === "string" && !raw.trim()) {
    issues.push({ field, code: "missing", message: `请填写${label}；没有持仓或额度时请明确填 0。` });
    return null;
  }
  if (typeof raw !== "string" || !/^\d{1,18}(?:\.\d+)?$/.test(raw.trim())) {
    issues.push({ field, code: "invalid_number", message: `${label}须为非负十进制数，整数部分不超过 18 位。` });
    return null;
  }
  const [whole, fraction = ""] = raw.trim().split(".");
  if (fraction.length > places) {
    issues.push({ field, code: "precision", message: `${label}最多支持 ${places} 位小数。` });
    return null;
  }
  return BigInt(whole) * 10n ** BigInt(places) + BigInt(fraction.padEnd(places, "0"));
}

/** Proportional allocation with deterministic largest-remainder rounding to cents. */
function allocateCents(amount: bigint, percentages: readonly bigint[]): bigint[] {
  const amounts = percentages.map((percentage) => amount * percentage / 10000n);
  const order = percentages.map((percentage, index) => ({ index, remainder: amount * percentage % 10000n }))
    .sort((a, b) => a.remainder === b.remainder ? a.index - b.index : a.remainder > b.remainder ? -1 : 1);
  let cents = amount - amounts.reduce((sum, item) => sum + item, 0n);
  for (const { index } of order) {
    if (cents === 0n) break;
    amounts[index] += 1n;
    cents -= 1n;
  }
  return amounts;
}

export function sizeEntryPlan(input: EntryPlanSizingInput): EntryPlanSizingResult {
  const issues: EntryPlanSizingIssue[] = [];
  const parsed = Object.fromEntries(Object.entries(MONEY_FIELDS).map(([field, label]) => [
    field, parseFixed(input[field as keyof typeof MONEY_FIELDS], field, label, 2, issues),
  ])) as Record<keyof typeof MONEY_FIELDS, bigint | null>;
  const entry = parseFixed(input.entryPriceCny, "entryPriceCny", "计划入场价", 6, issues);
  const stop = parseFixed(input.stopPriceCny, "stopPriceCny", "止损触发价", 6, issues);
  const percentages: bigint[] = [];
  if (!Array.isArray(input.batchPercentages) || input.batchPercentages.length === 0) {
    issues.push({ field: "batchPercentages", code: "missing", message: "请填写分批比例，合计须为 100%。" });
  } else if (input.batchPercentages.length > 20) {
    issues.push({ field: "batchPercentages", code: "inconsistent", message: "最多支持 20 批，请合并过细的分批计划。" });
  } else {
    input.batchPercentages.forEach((value, index) => {
      const field = `batchPercentages.${index}`;
      const percentage = parseFixed(value, field, `第 ${index + 1} 批比例`, 2, issues);
      if (percentage !== null) {
        if (percentage <= 0n || percentage > 10000n) issues.push({ field, code: "inconsistent", message: `第 ${index + 1} 批比例须大于 0 且不超过 100%。` });
        percentages.push(percentage);
      }
    });
    if (percentages.length === input.batchPercentages.length && percentages.reduce((sum, value) => sum + value, 0n) !== 10000n) {
      issues.push({ field: "batchPercentages", code: "inconsistent", message: "分批比例须精确合计为 100%，请调整后再试算。" });
    }
  }
  if (issues.length > 0) return { status: issues.every((issue) => issue.code === "missing") ? "incomplete" : "invalid", issues };

  // Null values necessarily added an issue above. Keep the check explicit for type safety.
  const { totalAssetsCny: total, cashAvailableCny: cash, instrumentLimitCny: limit, currentHoldingCny: holding, newRiskBudgetCny: risk } = parsed;
  if (total === null || cash === null || limit === null || holding === null || risk === null || entry === null || stop === null) {
    return { status: "incomplete", issues: [{ field: "input", code: "missing", message: "请完整填写资金与价格。" }] };
  }
  if (total <= 0n) issues.push({ field: "totalAssetsCny", code: "non_positive", message: "账户总资产须大于 0。" });
  if (entry <= 0n) issues.push({ field: "entryPriceCny", code: "non_positive", message: "计划入场价须大于 0。" });
  if (stop <= 0n || stop >= entry) issues.push({ field: "stopPriceCny", code: "inconsistent", message: "止损触发价须大于 0 且低于计划入场价。" });
  if (cash > total) issues.push({ field: "cashAvailableCny", code: "inconsistent", message: "可用现金不能超过账户总资产。" });
  if (holding > total || cash + holding > total) issues.push({ field: "currentHoldingCny", code: "inconsistent", message: "该标的持仓与可用现金之和不能超过账户总资产；请核对同一账户和日期的金额。" });
  if (limit > total) issues.push({ field: "instrumentLimitCny", code: "inconsistent", message: "该标的总投入上限不能超过账户总资产。" });
  if (holding > limit) issues.push({ field: "currentHoldingCny", code: "inconsistent", message: "现有持仓已超过该标的总投入上限，不能生成新增买入金额。" });
  if (risk > total) issues.push({ field: "newRiskBudgetCny", code: "inconsistent", message: "新增可承受亏损金额不能超过账户总资产。" });
  if (issues.length > 0) return { status: "invalid", issues };

  if (cash === 0n) issues.push({ field: "cashAvailableCny", code: "no_capacity", message: "没有可用现金，当前无新增买入额度。" });
  if (holding === limit) issues.push({ field: "instrumentLimitCny", code: "no_capacity", message: "现有持仓已达到该标的总投入上限，当前无新增买入额度。" });
  if (risk === 0n) issues.push({ field: "newRiskBudgetCny", code: "no_capacity", message: "新增可承受亏损金额为 0，当前无新增买入额度。" });
  if (issues.length > 0) return { status: "no_capacity", issues };

  const capitalCapacity = cash < limit - holding ? cash : limit - holding;
  // Price units cancel: integer cents are always rounded down at the risk boundary.
  const riskCapacity = risk * entry / (entry - stop);
  const amount = capitalCapacity < riskCapacity ? capitalCapacity : riskCapacity;
  const batches = allocateCents(amount, percentages);
  const notes = [
    "风险预算仅约束此次新增部分；现有持仓的亏损风险未纳入本次试算。",
    "按填写的入场价和止损价估算，不含手续费、税费、滑点或跳空；止损价不是保证成交价。",
    "金额试算不含交易单位与权限核验，不代表可成交股数；分批金额合计保持不超过新增投入额度。",
  ];
  if (batches.some((value) => value === 0n)) notes.push("部分批次分配后不足 0.01 元，显示为 0.00 元；请调整批次数或比例。");
  return {
    status: "ready",
    additionalAmountCny: fixed(amount),
    capitalCapacityCny: fixed(capitalCapacity),
    riskCapacityCny: fixed(riskCapacity),
    additionalPositionPct: fixed(amount * 10000n / total),
    totalPositionPct: fixed((holding + amount) * 10000n / total),
    plannedNewLossCny: fixed((amount * (entry - stop) + entry - 1n) / entry),
    batches: batches.map((value, index) => ({ percentage: fixed(percentages[index]), amountCny: fixed(value) })),
    notes,
  };
}
