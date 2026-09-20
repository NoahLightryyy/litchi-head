/** Translate the existing API error contract without exposing raw upstream errors. */
export function debateErrorMessage(error: unknown): string {
  if (!error || typeof error !== "object") return "分析请求失败，请稍后重试。";
  const value = error as { code?: unknown; status?: unknown; detail?: unknown };
  if (value.code === "NETWORK_ERROR") return "无法连接分析服务，请检查网络或后端连接。";
  if (value.status === 429) return "分析请求过于频繁，请稍后再试。";
  if (value.code === "EVIDENCE_INCOMPLETE") {
    const detail = value.detail && typeof value.detail === "object"
      ? value.detail as Record<string, unknown> : {};
    if (detail.capability === "stock_identity") {
      return "股票名称等基础信息尚未取得，AI 分析未启动。请先恢复个股数据，再重试。";
    }
    return "必要市场证据缺失、过期或存在冲突，AI 分析未启动。当前盘中分析还要求连续竞价时段；请查看数据来源诊断后重试。";
  }
  return "分析服务处理失败，请稍后重试；这不代表该股票已形成研究结论。";
}
