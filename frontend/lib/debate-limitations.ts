/** Consume the frozen DebateResult disclosures without inferring missing evidence. */
export function debateLimitations(result: {
  evidence_limitations?: { capability: string }[];
  review_report?: { overall_quality: number } | null;
  analyses?: { success: boolean }[];
} | null | undefined): string[] {
  if (!result) return [];
  const notes: string[] = [];
  const labels: Record<string, string> = { realtime_quote: "个股报价", news: "关联新闻" };
  const gaps = [...new Set((result.evidence_limitations ?? []).map(
    (item) => labels[item.capability] ?? item.capability,
  ))];
  if (gaps.length) notes.push(`${gaps.join("、")}证据不完整，以下为有限信息研究，未进入交易决策流程。`);
  if (result.review_report === null) notes.push("本次未取得有效独立评审，不能视为已完成全部复核。");
  const failed = (result.analyses ?? []).filter((item) => !item.success).length;
  if (failed) notes.push(`${failed} 位分析未成功，请结合可用分析与缺失信息判断。`);
  return notes;
}
