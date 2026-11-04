/** Only retire standalone source-count warnings; never rewrite a thesis, rating or mixed risk. */
const retiredWarnings = new Set([
  "行情为单源未交叉验证快照", "行情为单源未交叉验证", "单源行情未交叉验证",
  "单源行情未交叉核验", "单源报价未交叉验证", "单源未交叉验证快照",
  "单源未交叉验证", "单源，未交叉验证", "单源行情，未交叉验证", "单源",
]);
export function marketLimitationsView(original: string): {text: string; original: string; changed: boolean} {
  const parts = original.split(/([；;。\n])/);
  let changed = false;
  for (let i = 0; i < parts.length; i += 2) {
    if (retiredWarnings.has(parts[i].trim())) {
      parts[i] = "";
      if (i + 1 < parts.length) parts[i + 1] = "";
      changed = true;
    }
  }
  return {text: changed ? parts.join("").trim() || "无其他已记录限制。" : original, original, changed};
}
export const MARKET_SOURCE_NOTICE = "行情规则：一个有效来源即可用于分析，不把单源本身当作风险。仍检查数据时间、价格异常和来源冲突。历史观点不会自动重算，旧评分与方向保持原样。";
