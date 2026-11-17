"use client";

import { useState, useSyncExternalStore } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { DebateResult, InstrumentType } from "@/lib/types/debate";
import { debateInstrumentMatches } from "@/lib/debate-instrument";
import { CONDITION_STATUS, ENTRY_HORIZONS, ENTRY_STATUS, generateEntryPlan, readEntryPlan, type EntryHorizon, type EntryPlanResult, type HorizonEntryPlan } from "@/lib/entry-plan";
import { sizeEntryPlan, type EntryPlanSizingInput, type EntryPlanSizingResult } from "@/lib/entry-plan-sizing";

const button = "rounded-md border border-bg-tertiary px-3 py-2 text-sm text-accent-blue disabled:opacity-50";
const inputClass = "mt-1 w-full rounded-md border border-bg-tertiary bg-bg-primary px-3 py-2 text-sm";
const money = (value: string) => value.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const date = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
function subscribeOnline(listener: () => void) {
  window.addEventListener("online", listener);
  window.addEventListener("offline", listener);
  return () => { window.removeEventListener("online", listener); window.removeEventListener("offline", listener); };
}

export function EntryPlanPanel({ result, instrumentType }: { result: DebateResult; instrumentType: InstrumentType }) {
  if (!debateInstrumentMatches(result, result.stock_code, instrumentType)) {
    return <p role="alert">当前分析身份不一致，无法读取入场计划。</p>;
  }
  return <SessionEntryPlanPanel key={`${instrumentType}:${result.stock_code}:${result.session_id}`} result={result} instrumentType={instrumentType} />;
}

function SessionEntryPlanPanel({ result, instrumentType }: { result: DebateResult; instrumentType: InstrumentType }) {
  const client = useQueryClient();
  const online = useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
  const [horizon, setHorizon] = useState<EntryHorizon>("short");
  const identity = { sessionId: result.session_id, stockCode: result.stock_code, instrumentType };
  const queryKey = ["entry-plan", instrumentType, result.stock_code, result.session_id];
  const query = useQuery({
    queryKey, queryFn: ({ signal }) => readEntryPlan(identity, signal),
    retry: false, staleTime: Infinity, refetchOnWindowFocus: false,
  });
  const generation = useMutation({
    mutationFn: (refresh: boolean) => {
      if (typeof navigator !== "undefined" && !navigator.onLine) throw new Error("当前离线，请联网后手动生成计划。");
      return generateEntryPlan(identity, refresh);
    },
    retry: false, networkMode: "always",
    onSuccess: (data) => client.setQueryData(queryKey, data),
  });
  const failure = generation.error ?? query.error;
  return <EntryPlanContent
    name={result.stock_name} data={query.data ?? null} horizon={horizon} onHorizon={setHorizon}
    loading={query.isPending} reading={query.isFetching} generating={generation.isPending}
    offline={!online || query.fetchStatus === "paused"}
    error={failure instanceof Error ? failure.message : null}
    canGenerate={query.isSuccess || !!query.data}
    onRead={() => { generation.reset(); void query.refetch(); }}
    onGenerate={() => generation.mutate(Boolean(query.data))}
  />;
}

export interface EntryPlanContentProps {
  name: string;
  data: EntryPlanResult | null;
  horizon: EntryHorizon;
  onHorizon: (horizon: EntryHorizon) => void;
  loading: boolean;
  reading: boolean;
  generating: boolean;
  offline: boolean;
  error: string | null;
  canGenerate: boolean;
  onRead: () => void;
  onGenerate: () => void;
}

/** Kept separate from transport so all availability states have the same view. */
export function EntryPlanContent(props: EntryPlanContentProps) {
  const { data, horizon, loading, reading, generating, offline, error } = props;
  const plan = data?.plans.find((item) => item.horizon === horizon);
  const marketTimes = [...new Set(data?.evidence.filter((source) => source.kind !== "analysis")
    .map((source) => `${source.kind === "quote" ? "报价" : "日线"} ${source.data_time}`) ?? [])];
  return <section aria-label="买入观察信号与资金计划" className="mb-5 rounded-xl border border-accent-blue/30 bg-bg-secondary p-4 sm:p-5 space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="font-semibold">买入观察信号与资金计划</h3><p className="mt-1 text-sm text-text-muted">{props.name} · 在已完成辩论上补充入场、止损与分批条件，不重跑辩论。</p></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={button} disabled={reading || generating || offline} onClick={props.onRead}>{reading ? "正在读取…" : "读取已保存计划"}</button>
        <button type="button" className={`${button} bg-accent-blue text-white`} disabled={!props.canGenerate || loading || generating || offline} onClick={props.onGenerate}>{generating ? "正在生成计划…" : data ? "更新条件计划" : "生成条件计划"}</button>
      </div>
    </header>
    <p className="text-xs text-text-muted">生成或更新会调用 AI；读取已保存计划不产生推理费用，失败后不会自动重试生成。</p>
    {offline && <p role="status" className="text-sm">当前离线。{data ? "保留上次计划，资金试算仍可使用。" : "联网后继续读取已保存计划。"}</p>}
    {loading && !data && !offline && <p role="status">正在读取本次辩论的入场计划…</p>}
    {generating && <p role="status" className="text-sm">正在补采行情并生成三个周期的条件计划，请勿重复提交。{data ? "下方暂保留上次计划。" : ""}</p>}
    {error && <p role="alert" className="rounded-md bg-amber-500/10 p-3 text-sm">{data ? "本次更新未完成，保留上次计划。" : ""}{error}</p>}
    {!data && !loading && !generating && !error && <p className="text-sm text-text-secondary">这份辩论尚无入场计划。点击「生成条件计划」补充具体触发条件；原有走势观点继续保留在下方。</p>}
    {data && plan && <>
      <div role="group" aria-label="入场计划周期" className="flex flex-wrap gap-2">{(Object.entries(ENTRY_HORIZONS) as [EntryHorizon, string][]).map(([key, label]) => <button key={key} type="button" aria-pressed={key === horizon} className={`${button} ${key === horizon ? "border-accent-blue bg-accent-blue/10 font-semibold" : ""}`} onClick={() => props.onHorizon(key)}>{label}</button>)}</div>
      <article aria-label={`${ENTRY_HORIZONS[horizon]}入场条件`} className="space-y-4">
        <div><h4 className="font-semibold text-accent-blue">{ENTRY_STATUS[plan.status]}</h4><p className="mt-1 text-sm">{plan.summary}</p><p className="mt-2 text-xs text-text-muted">AI 按所示数据核对，未持续监测。{plan.status === "consider" ? "当前记录可供关注，仍需核对最新行情与条件。" : ""}</p><p aria-label="计划使用的行情时间" className="mt-1 text-xs text-text-muted">行情数据时间：{marketTimes.length ? marketTimes.join("；") : "暂无可用行情资料"}</p></div>
        <ul className="space-y-2">{plan.conditions.map((condition, index) => <li key={index} className="rounded-md border border-bg-tertiary p-3 text-sm">
          <p><span className={`mr-2 font-medium ${condition.status === "met" ? "text-accent-blue" : "text-text-secondary"}`}>{CONDITION_STATUS[condition.status]}</span>{condition.condition}</p>
          <p className="mt-1 text-text-muted">{condition.explanation}</p>
        </li>)}</ul>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md bg-bg-primary/50 p-3"><h5 className="text-sm font-medium">候选入场区间 / 元</h5><p className="mt-1 font-number text-xl">{plan.entry_low === null ? "尚无有据价格" : `${plan.entry_low}–${plan.entry_high}`}</p></div>
          <div className="rounded-md bg-bg-primary/50 p-3"><h5 className="text-sm font-medium">候选止损触发价 / 元</h5><p className="mt-1 font-number text-xl">{plan.stop_loss ?? "尚无有据价格"}</p></div>
        </div>
        <p className="text-sm text-text-secondary">价格依据：{plan.price_basis}</p>
        <div><h5 className="text-sm font-semibold">停止入场或暂停后续批次的条件</h5><ul className="mt-1 list-disc pl-5 text-sm space-y-1">{plan.invalidation.map((text, index) => <li key={index}>{text}</li>)}</ul></div>
        <div><h5 className="text-sm font-semibold">分批买入条件</h5><ol className="mt-2 space-y-2 text-sm">{plan.batches.map((batch, index) => <li key={index} className="rounded-md border border-bg-tertiary p-3"><strong>第 {index + 1} 批 · 计划预算的 {batch.budget_pct}%</strong><p className="mt-1">{batch.trigger}</p></li>)}</ol><p className="mt-2 text-xs text-text-muted">比例针对本次计划预算；不代表账户总资产仓位。{plan.position_note}</p></div>
        <details className="rounded-md border border-bg-tertiary p-3 text-sm"><summary className="cursor-pointer">查看资料时间、依据与限制</summary><div className="mt-3 space-y-3">
          <p>原辩论研究：{date(data.source_research_generated_at)}；本计划生成：{date(data.generated_at)}（北京时间）</p>
          <p className="text-xs text-text-muted">模型：{data.model}。生成时间不代表行情时间。</p>
          {data.evidence.map((source) => <details key={source.id}><summary className="cursor-pointer">{source.id} · {source.title} · 数据时间 {source.data_time}{source.kind === "analysis" ? " · 既有 AI 研究" : ""}</summary><p className="mt-2 whitespace-pre-wrap text-xs text-text-muted">{source.content}</p></details>)}
          <ul className="list-disc pl-5">{plan.conditions.map((condition, index) => <li key={index}>条件 {index + 1} 引用：{condition.evidence_ids.join("、")}</li>)}{plan.price_evidence_ids.length > 0 && <li>候选价格引用：{plan.price_evidence_ids.join("、")}</li>}</ul>
          <ul className="list-disc pl-5">{[...new Set([...plan.limitations, ...data.gaps])].map((text, index) => <li key={index}>{text}</li>)}</ul>
        </div></details>
      </article>
      <AmountScenario key={`${data.generated_at}:${horizon}`} plan={plan} />
    </>}
  </section>;
}

const fields = [
  ["totalAssetsCny", "账户总资产（元，含现金与持仓）"],
  ["cashAvailableCny", "可用现金（元）"],
  ["instrumentLimitCny", "该标的总投入上限（元）"],
  ["currentHoldingCny", "该标的现有持仓市值（元，无持仓请填 0）"],
  ["newRiskBudgetCny", "此次新增可承受亏损金额（元）"],
  ["entryPriceCny", "试算入场价（元，可编辑）"],
  ["stopPriceCny", "试算止损触发价（元，可编辑）"],
] as const;

export function AmountScenario({ plan }: { plan: HorizonEntryPlan }) {
  const [values, setValues] = useState<EntryPlanSizingInput>(() => ({
    totalAssetsCny: "", cashAvailableCny: "", instrumentLimitCny: "", currentHoldingCny: "", newRiskBudgetCny: "",
    entryPriceCny: plan.entry_high === null ? "" : String(plan.entry_high),
    stopPriceCny: plan.stop_loss === null ? "" : String(plan.stop_loss),
    batchPercentages: plan.batches.map((batch) => String(batch.budget_pct)),
  }));
  const [result, setResult] = useState<EntryPlanSizingResult | null>(null);
  return <form aria-label="本地资金与风险试算" className="space-y-4 border-t border-bg-tertiary pt-4" onSubmit={(event) => { event.preventDefault(); setResult(sizeEntryPlan(values)); }}>
    <div><h4 className="font-semibold">填写资金，试算仓位与每批金额</h4><p className="mt-1 text-sm text-text-muted">资金只在当前页面计算，不发送给 AI 或服务器。切换周期或更新计划会清空试算输入。</p></div>
    <p className="text-xs text-text-muted">{plan.entry_high === null ? "当前没有候选价格，可手动填写价格做情景试算。" : "入场价预填候选区间上沿，止损价预填本周期候选值，均可编辑。"}手动改价仅影响试算，不改变上方 AI 条件状态。</p>
    <p className="text-sm text-text-secondary">各批按同一输入价格估算；后续批次价格变化时须重新计算。</p>
    <div className="grid gap-3 sm:grid-cols-2">{fields.map(([field, label]) => <label key={field} className="text-sm">{label}<input className={inputClass} inputMode="decimal" autoComplete="off" value={values[field]} onChange={(event) => { setValues({ ...values, [field]: event.target.value }); setResult(null); }} /></label>)}</div>
    <fieldset><legend className="text-sm font-medium">每批占本次计划预算的比例（合计 100%）</legend><div className="mt-2 grid gap-3 sm:grid-cols-2">{values.batchPercentages.map((percentage, index) => <label key={index} className="text-sm">第 {index + 1} 批比例（%）<input className={inputClass} inputMode="decimal" value={percentage} onChange={(event) => { setValues({ ...values, batchPercentages: values.batchPercentages.map((value, i) => i === index ? event.target.value : value) }); setResult(null); }} /></label>)}</div></fieldset>
    <button type="submit" className={`${button} border-accent-blue`}>计算新增仓位与分批金额</button>
    {result && result.status !== "ready" && <ul role="alert" className="list-disc pl-5 text-sm text-accent-red space-y-1">{result.issues.map((issue, index) => <li key={`${issue.field}:${index}`}>{issue.message}</li>)}</ul>}
    {result?.status === "ready" && <div role="status" className="rounded-lg border border-bg-tertiary bg-bg-primary/50 p-4 space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">{[["此次新增投入上限", `¥${money(result.additionalAmountCny)}`], ["新增仓位 / 总资产", `${result.additionalPositionPct}%`], ["含现有持仓 / 总资产", `${result.totalPositionPct}%`]].map(([label, value]) => <div key={label}><p className="text-xs text-text-muted">{label}</p><p className="mt-1 font-number text-xl">{value}</p></div>)}</div>
      <p className="text-sm">新增部分按止损价测算亏损：¥{money(result.plannedNewLossCny)}。现有持仓风险未纳入，金额尚未计入费用与滑点。</p>
      <p className="text-sm text-text-secondary">各批按同一输入价格估算；后续批次价格变化时须重新计算。</p>
      <ol className="space-y-2 text-sm">{result.batches.map((batch, index) => <li key={index}><strong>第 {index + 1} 批：¥{money(batch.amountCny)} · {batch.percentage}%</strong><p>{plan.batches[index].trigger}</p></li>)}</ol>
      <details className="text-xs text-text-muted"><summary className="cursor-pointer">查看计算约束与口径</summary><p className="mt-2">现金及标的投入上限允许 ¥{money(result.capitalCapacityCny)}；新增风险预算允许 ¥{money(result.riskCapacityCny)}。取两者较小值，金额向下取整到分。</p><ul className="mt-2 list-disc pl-5 space-y-1">{result.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </form>;
}
