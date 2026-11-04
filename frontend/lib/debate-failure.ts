/** Display-only classification of returned errors, never a direction or a retry trigger. */
export interface AnalysisOutcome { success: boolean; error?: string | null }

export function isBalanceFailure(error: string | null | undefined): boolean {
  return /LLM_INSUFFICIENT_BALANCE|insufficient_balance_error|\binsufficient\s+balance\b/i.test(error ?? "");
}

export function analysisFailureMessage(error: string | null | undefined): string {
  if (isBalanceFailure(error)) return "模型服务余额不足";
  // Legacy errors wrapped HTTP failures as parse errors: prefer the request cause.
  if (/LLM_REQUEST_FAILED|Error code:\s*\d{3}|HTTP\s+[45]\d{2}|ConnectionError|TimeoutError/.test(error ?? "")) return "模型服务请求失败";
  if (/解析失败|validation error|返回类型不匹配/.test(error ?? "")) return "模型返回内容未通过校验";
  return "分析未成功（未保存明确原因）";
}

export function noResearchMessage(analyses: AnalysisOutcome[]): string {
  return analyses.some(a => !a.success && isBalanceFailure(a.error))
    ? "模型服务余额不足，本次未生成研究结论。请先处理模型账户余额，再手动发起分析；刷新行情不会解决，也不会自动重跑付费分析。"
    : "本次没有成功返回的流派分析，未生成研究结论。这不是看涨、看跌或中性的判断；请查看下方失败原因。";
}
