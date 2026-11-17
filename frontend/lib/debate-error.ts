/** Translate the existing API error contract without exposing raw upstream errors. */
export function debateErrorMessage(error: unknown, instrumentType: "stock" | "etf" = "stock"): string {
  if (!error || typeof error !== "object") return "分析请求失败，请稍后重试。";
  const value = error as { code?: unknown; status?: unknown; detail?: unknown };
  if (value.code === "ANALYSIS_BALANCE_INSUFFICIENT") return "模型服务余额不足，本次未生成研究结论。请先处理模型账户余额，再手动发起分析；不会自动重跑。";
  if (value.code === "ANALYSIS_NETWORK_UNAVAILABLE") return "网络连接中断，未能连上模型服务，本次未生成研究结论。请确认网络恢复后手动重新分析；不会自动重跑。";
  if (value.code === "ANALYSIS_FAILED") return "本次没有成功返回的流派分析，未生成研究结论。请查看服务诊断。";
  if (value.code === "NETWORK_ERROR") return "无法连接分析服务，请检查网络或后端连接。";
  if (value.status === 429) return "分析请求过于频繁，请稍后再试。";
  if (value.code === "ETF_NOT_FOUND") return "未在基金目录中找到该 ETF，分析未启动。请确认代码后重试。";
  if (value.code === "INSTRUMENT_TYPE_MISMATCH") return "该代码属于 ETF，请从 ETF 详情页启动辩论。";
  if (value.code === "ANALYSIS_NOT_CONFIGURED") {
    return "DeepSeek 分析服务尚未配置。请在后端配置有效的 API 凭据并重启服务，再启动分析；重复点击不会恢复。";
  }
  if (value.code === "EVIDENCE_INCOMPLETE") {
    const detail = value.detail && typeof value.detail === "object"
      ? value.detail as Record<string, unknown> : {};
    if (detail.capability === "etf_research") return "ETF 资料暂不可用，分析未启动。可刷新行情、K线或相关资料后重试。";
    if (detail.capability === "stock_identity") {
      return "股票名称等基础信息尚未取得，AI 分析未启动。请先恢复个股数据，再重试。";
    }
    return "必要市场证据缺失、过期或存在冲突，AI 分析未启动。当前盘中分析还要求连续竞价时段；请查看数据来源诊断后重试。";
  }
  return instrumentType === "etf"
    ? "分析服务处理失败，请稍后重试；本次未形成 ETF 研究结论。"
    : "分析服务处理失败，请稍后重试；这不代表该股票已形成研究结论。";
}
