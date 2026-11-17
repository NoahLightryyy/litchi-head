/** Display-only classification of returned errors, never a direction or a retry trigger. */
export interface AnalysisOutcome { success: boolean; error?: string | null }

export function isBalanceFailure(error: string | null | undefined): boolean {
  return /LLM_INSUFFICIENT_BALANCE|insufficient_balance_error|\binsufficient\s+balance\b/i.test(error ?? "");
}

/** 只认后端的明确代码：笼统的请求失败不能当成断网。 */
export function isNetworkFailure(error: string | null | undefined): boolean {
  return /LLM_NETWORK_UNAVAILABLE/.test(error ?? "");
}

export function isTimeoutFailure(error: string | null | undefined): boolean {
  return /LLM_REQUEST_TIMEOUT|执行超时/.test(error ?? "");
}

/** 部分失败时放在摘要前面的原因；没有明确原因就不写。 */
export function failureReasonSummary(analyses: AnalysisOutcome[]): string {
  const failed = analyses.filter(a => !a.success);
  const reasons: string[] = [];
  if (failed.some(a => isBalanceFailure(a.error))) reasons.push("模型服务余额不足");
  if (failed.some(a => isNetworkFailure(a.error))) reasons.push("分析期间网络连接中断");
  if (failed.some(a => isTimeoutFailure(a.error))) reasons.push("部分分析超时");
  return reasons.length ? `${reasons.join("，")}；` : "";
}

export function analysisFailureMessage(error: string | null | undefined): string {
  if (isBalanceFailure(error)) return "模型服务余额不足";
  if (isNetworkFailure(error)) return "网络连接中断，未能连上模型服务";
  if (isTimeoutFailure(error)) return "分析超时，未在限定时间内完成";
  // Legacy errors wrapped HTTP failures as parse errors: prefer the request cause.
  if (/LLM_REQUEST_FAILED|Error code:\s*\d{3}|HTTP\s+[45]\d{2}|ConnectionError|TimeoutError/.test(error ?? "")) return "模型服务请求失败";
  if (/解析失败|validation error|返回类型不匹配/.test(error ?? "")) return "模型返回内容未通过校验";
  return "分析未成功（未保存明确原因）";
}

export function noResearchMessage(analyses: AnalysisOutcome[]): string {
  if (analyses.some(a => !a.success && isBalanceFailure(a.error))) {
    return "模型服务余额不足，本次未生成研究结论。请先处理模型账户余额，再手动发起分析；刷新行情不会解决，也不会自动重跑付费分析。";
  }
  if (analyses.some(a => !a.success && isNetworkFailure(a.error))) {
    return "分析期间网络连接中断，未能连上模型服务，本次未生成研究结论。请确认网络恢复后手动重新分析；不会自动重跑付费分析。";
  }
  return "本次没有成功返回的流派分析，未生成研究结论。这不是看涨、看跌或中性的判断；请查看下方失败原因。";
}
