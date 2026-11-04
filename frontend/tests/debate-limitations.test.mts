import test from "node:test";
import assert from "node:assert/strict";
import { debateLimitations, type DebateNoticeInput } from "../lib/debate-limitations.ts";

const closing = "休市研究：使用官方交易日历核验的最近交易日收盘报价，数据时间 2026-10-26T16:11:47+08:00；来源 eastmoney, sina（2 源价格一致），不是实时行情；不进入交易决策。";
const sample = (source: string, count = 0) => `${source} 新闻样本时间范围 2026-10-26T17:58:32+08:00 至 2026-10-27T01:09:16.110857+08:00，匹配 ${count} 条；未覆盖完整近 3 天（样本不证明连续覆盖），不能据此认定该时段无新闻。`;
const fixture = (): DebateNoticeInput => ({ evidence_limitations: [
  { capability: "realtime_quote", research_note: closing, source_statuses: { "direct-eastmoney-quote": "stale", "direct-sina-quote": "stale" }, error_codes: ["market_not_in_continuous_auction"] },
  { capability: "news", research_note: ["sina", "caixin", "sina", "eastmoney", "cls", "ths", "futu"].map((source) => sample(source)).join(" "), error_codes: ["latest_sample_only", "rolling_window_not_fully_covered"] },
], review_report: { overall_quality: 0.78 }, analyses: Array.from({ length: 5 }, () => ({ success: true })) });

test("七段样本说明收敛为行情与新闻两点，完整诊断保留，不把休市当研究失败", () => {
  const input = fixture(), result = debateLimitations(input);
  assert.equal(result.highlights.length, 2);
  assert.ok(result.highlights.every((item) => item.tone === "info"));
  const text = result.highlights.map((item) => item.message).join(" ");
  assert.ok(text.length < 150);
  assert.match(text, /2026-10-26 16:11（北京时间）/);
  assert.match(text, /本次新闻样本未匹配到相关报道/);
  assert.match(text, /近期事件仍可能遗漏/);
  assert.doesNotMatch(text, /不是实时行情|有限信息研究|匹配 0 条|未进入交易决策|01:09/);
  assert.equal(result.researchOnly, true);
  assert.equal(result.diagnostics[1].notes[0], input.evidence_limitations![1].research_note);
  assert.deepEqual(result.diagnostics[1].codes, ["latest_sample_only", "rolling_window_not_fully_covered"]);
});

test("新闻来源计数不相加，存在匹配时不显示零匹配；未知覆盖不推断为无新闻", () => {
  const result = debateLimitations({ evidence_limitations: [{ capability: "news", research_note: `${sample("sina", 2)} ${sample("sina", 2)} ${sample("cls", 0)}` }] });
  assert.doesNotMatch(result.highlights[0].message, /未匹配|4 条|没有新闻|已取得/);
  assert.match(result.highlights[0].message, /覆盖范围有限/);
  const unknown = debateLimitations({ evidence_limitations: [{ capability: "news", research_note: "新浪新闻覆盖范围有限，未记录匹配数量。" }] });
  assert.doesNotMatch(unknown.highlights[0].message, /未匹配|没有新闻|已取得/);
});

test("真正的校验冲突优先显示，不能被休市说明降级；请求失败仍提醒", () => {
  for (const fields of [{ error_codes: ["quote_price_conflict"] }, { source_statuses: { sina: "conflicted" } }, { error_codes: ["quote_timestamp_in_future"] }]) {
    const result = debateLimitations({ evidence_limitations: [{ capability: "realtime_quote", research_note: closing, ...fields }] });
    assert.equal(result.highlights[0].tone, "danger");
    assert.match(result.highlights[0].message, /冲突或校验异常/);
    assert.doesNotMatch(result.highlights[0].message, /采用/);
  }
  const failed = debateLimitations({ evidence_limitations: [{ capability: "news", research_note: sample("sina"), source_statuses: { sina: "failed" } }] });
  assert.equal(failed.highlights[0].tone, "warning");
  assert.match(failed.highlights[0].message, /部分新闻来源未取得/);
});

test("评审缺失与分析失败突出展示，能力缺失兼容旧结果", () => {
  const result = debateLimitations({ evidence_limitations: [{ capability: "news" }], review_report: null, analyses: [{ success: true }, { success: false }] });
  assert.ok(result.highlights.every((item) => item.tone === "warning"));
  const text = result.highlights.map((item) => item.message).join(" ");
  assert.match(text, /新闻资料不完整/);
  assert.match(text, /未取得有效独立评审/);
  assert.match(text, /1 位分析未成功/);
  assert.deepEqual(debateLimitations(undefined), { highlights: [], diagnostics: [], researchOnly: false });
  assert.equal(debateLimitations({ review_report: { overall_quality: 0.8 }, analyses: [{ success: true }] }).highlights.length, 0);
  assert.equal(debateLimitations({}).highlights.length, 0);
});

test("仅格式化明确行情时刻，未知旧时间不拿采集时间补填，单源照常研究", () => {
  const result = debateLimitations({ evidence_limitations: [{ capability: "realtime_quote", research_note: "休市研究：09/30 收盘报价，新浪单源，未交叉验证。" }] });
  assert.equal(result.highlights[0].tone, "info");
  assert.match(result.highlights[0].message, /时间见详情/);
  assert.doesNotMatch(result.highlights[0].message, /最近|最新|无法研究/);
  for (const timestamp of ["2026-02-30T16:11:47+08:00", "2026-13-01T16:11:47+08:00", "2026-10-26T16:11:47", "not-a-date"]) {
    const input = { evidence_limitations: [{ capability: "realtime_quote", collected_at: "2030-01-01T00:00:00Z", research_note: closing.replace("2026-10-26T16:11:47+08:00", timestamp) }] };
    const text = debateLimitations(input).highlights[0].message;
    assert.match(text, /时间见详情/);
    assert.doesNotMatch(text, /2030|Invalid Date/);
  }
  const utc = debateLimitations({ evidence_limitations: [{ capability: "realtime_quote", research_note: closing.replace("2026-10-26T16:11:47+08:00", "2026-10-26T08:11:47Z") }] });
  assert.match(utc.highlights[0].message, /2026-10-26 16:11/);
});

test("ETF范围是说明，缺少报价或日线是具体缺口；未知限制不消失", () => {
  const result = debateLimitations({ evidence_limitations: [
    { capability: "etf_research_scope", research_note: "研究范围说明" },
    { capability: "etf_daily", research_note: "日线缺失" },
    { capability: "etf_quote" }, { capability: "etf_related" },
    { capability: "custom", research_note: "新能力尚未完成核查" },
  ] });
  assert.equal(result.highlights.at(-1)?.tone, "info");
  assert.equal(result.highlights.filter((item) => item.tone === "warning").length, 4);
  assert.ok(result.highlights.some((item) => item.message.includes("未取得历史日线")));
  assert.equal(result.diagnostics.find((item) => item.capability === "custom")?.notes[0], "新能力尚未完成核查");
});

test("同能力重复说明去重且保留不同诊断；重要提醒排在一般说明前", () => {
  const input = fixture();
  input.evidence_limitations!.push({ ...input.evidence_limitations![1] });
  input.review_report = null;
  const result = debateLimitations(input);
  assert.equal(result.diagnostics.length, 2);
  assert.equal(result.diagnostics[1].notes.length, 1);
  assert.equal(result.highlights[0].label, "独立评审");
  assert.equal(result.highlights[0].tone, "warning");
});


test("billing failure has a concrete cause, including legacy wrapped errors", () => {
 const result=debateLimitations({analyses:Array.from({length:5},()=>({success:false,error:"LLM 结构化输出解析失败: Error code: 402 - Insufficient Balance secret"})),review_report:null});
 const text=result.highlights.map(item=>item.message).join(" ");
 assert.match(text,/余额不足/); assert.match(text,/没有.*研究结论|未生成研究结论/);
 assert.doesNotMatch(text,/当前结论只包含|secret|尚缺这一步复核/);
 assert.equal(result.highlights[0].tone,"danger");
});
