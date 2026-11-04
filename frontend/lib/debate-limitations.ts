import { isBalanceFailure, noResearchMessage } from "./debate-failure.ts";

/** Present the frozen disclosures; never turn a display summary into a trading gate. */
export interface DebateNoticeInput {
  evidence_limitations?: {
    capability: string;
    research_note?: string | null;
    source_statuses?: Record<string, string>;
    error_codes?: string[];
  }[];
  review_report?: { overall_quality: number } | null;
  analyses?: { success: boolean; error?: string | null }[];
}

export interface DebateNoticeItem {
  label: string;
  message: string;
  tone: "info" | "warning" | "danger";
}

interface Diagnostic {
  capability: string;
  label: string;
  notes: string[];
  sources: string[];
  codes: string[];
}

const labels: Record<string, string> = {
  realtime_quote: "行情依据", news: "新闻范围", kline_business: "走势资料",
  etf_quote: "ETF 场内报价", etf_daily: "ETF 历史日线",
  etf_related: "相关资料", etf_research_scope: "ETF 研究范围",
};
const statuses: Record<string, string> = {
  success_data: "已取得数据", success_empty: "返回为空", failed: "请求失败",
  unsupported: "暂不支持", stale: "未满足实时性或覆盖要求", conflicted: "数据冲突",
  unavailable: "未取得", empty: "返回为空",
};
const criticalCodes = /conflict|corrupt|suspect|identity|checksum|cardinality|timestamp_(?:in_future|missing)/;

/** Only a timestamp explicitly attached to the quote is a quote time, not collected_at. */
function closingQuoteTime(note: string): string | null {
  const value = note.match(/数据时间\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))/)?.[1];
  if (!value || !Number.isFinite(Date.parse(value))) return null;
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  if (new Date(Date.UTC(year, month - 1, day)).toISOString().slice(0, 10) !== value.slice(0, 10)) return null;
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(value));
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}（北京时间）`;
}

function summarize(items: NonNullable<DebateNoticeInput["evidence_limitations"]>, diagnostic: Diagnostic): DebateNoticeItem {
  const { label, capability, notes, codes } = diagnostic;
  const values = items.flatMap((item) => Object.values(item.source_statuses ?? {}));
  const critical = values.includes("conflicted") || codes.some((code) => criticalCodes.test(code))
    || notes.some((note) => note.includes("最近收盘报价来源价格冲突，未用于研究"));
  if (critical) return { label, tone: "danger", message: "数据存在冲突或校验异常；依赖这些数据的结论需要重新核查。" };
  const failed = values.some((value) => value === "failed" || value === "unavailable");
  const closing = notes.find((note) => /^休市研究：.*收盘报价/.test(note));
  if (capability === "realtime_quote" && closing) {
    const time = closingQuoteTime(closing);
    return { label, tone: "info", message: `采用${time ? ` ${time}的收盘报价` : "已保存的收盘报价（时间见详情）"}用于本次研究；下单前需刷新报价。` };
  }
  if (capability === "news" && notes.length && notes.every((note) => /新闻样本时间范围|新闻覆盖/.test(note))) {
    const counts = notes.flatMap((note) => [...note.matchAll(/匹配\s*(\d+)\s*条/g)].map((match) => Number(match[1])));
    // Different adapters may contain the same story: never sum their match counts.
    const noMatches = notes.every((note) => /匹配\s*\d+\s*条/.test(note))
      && counts.length > 0 && counts.every((count) => count === 0);
    return {
      label, tone: failed ? "warning" : "info",
      message: failed ? "部分新闻来源未取得；近期事件相关判断需补充核查。"
        : noMatches ? "本次新闻样本未匹配到相关报道；近期事件仍可能遗漏。"
          : "新闻覆盖范围有限；涉及近期事件的判断需补充核查。",
    };
  }
  const messages: Record<string, string> = {
    realtime_quote: "本次报价资料不完整；涉及当前价格的判断需核对最新行情。",
    news: "新闻资料不完整，近期事件相关判断需补充核查。",
    kline_business: "走势资料不完整；相关技术指标与价格条件需核查。",
    etf_quote: "未取得场内报价；本次不能判断当前价格与涨跌。",
    etf_daily: "未取得历史日线；本次不能据此判断技术指标与走势。",
    etf_related: "本轮未取得匹配资料；政策与事件相关判断需补充资料。",
    etf_research_scope: "本次围绕场内行情与主题资料研究；净值、实际持仓和跟踪情况尚待核验。",
  };
  return {
    label, tone: capability === "etf_research_scope" ? "info" : "warning",
    message: messages[capability] ?? "部分研究资料存在限制；使用相关结论前请查看来源详情。",
  };
}

export function debateLimitations(result: DebateNoticeInput | null | undefined): {
  highlights: DebateNoticeItem[]; diagnostics: Diagnostic[]; researchOnly: boolean;
} {
  const highlights: DebateNoticeItem[] = [];
  const diagnostics: Diagnostic[] = [];
  const limitations = result?.evidence_limitations ?? [];
  for (const capability of new Set(limitations.map((item) => item.capability))) {
    const items = limitations.filter((item) => item.capability === capability);
    const diagnostic: Diagnostic = {
      capability, label: labels[capability] ?? "研究资料",
      notes: [...new Set(items.map((item) => item.research_note?.trim()).filter((note): note is string => Boolean(note)))],
      sources: [...new Set(items.flatMap((item) => Object.entries(item.source_statuses ?? {}).map(
        ([name, status]) => `${name}：${statuses[status] ?? status}`,
      )))],
      codes: [...new Set(items.flatMap((item) => item.error_codes ?? []))],
    };
    diagnostics.push(diagnostic);
    highlights.push(summarize(items, diagnostic));
  }
  const analyses = result?.analyses ?? [];
  const allFailed = analyses.length > 0 && !analyses.some(item => item.success === true);
  if (!allFailed && result?.review_report === null) highlights.push({ label: "独立评审", tone: "warning", message: "本次未取得有效独立评审，结论尚缺这一步复核。" });
  const failed = (result?.analyses ?? []).filter((item) => item.success === false).length;
  if (failed) highlights.push({ label: "分析完成情况", tone: allFailed ? "danger" : "warning",
    message: allFailed ? `${failed} 位分析未成功。${noResearchMessage(analyses)}`
      : `${analyses.some(a => !a.success && isBalanceFailure(a.error)) ? "模型服务余额不足；" : ""}${failed} 位分析未成功，当前结论只包含已完成的分析。`,
  });
  const priority = { danger: 0, warning: 1, info: 2 };
  highlights.sort((a, b) => priority[a.tone] - priority[b.tone]);
  return { highlights, diagnostics, researchOnly: limitations.length > 0 };
}
