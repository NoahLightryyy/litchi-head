/** Explicit UI translations; source content is never machine-translated implicitly. */
export type Locale = "zh-CN" | "en";
export const LOCALE_COOKIE = "litchi-locale";
export function normalizeLocale(value: unknown): Locale { return value === "en" ? "en" : "zh-CN"; }
export const EN_MESSAGES: Readonly<Record<string, string>> = {
  "搜索与发现": "Search & discover",
  "市场总览": "Market overview", "行业研究": "Industry research", "选股与对比": "Screen & compare",
  "自选与跟踪": "Watchlist", "持仓与风险": "Portfolio & risk", "研究与复盘": "Research & review",
  "数据状态": "Data status", "设置": "Settings", "工具与设置": "Tools & settings",
  "最近浏览": "Recently viewed", "暂无记录": "No recent activity", "个股": "Stock", "板块": "Sector",
  "板块研究 · 新浪分类": "Sector research · Sina categories", "数据来源": "Data source",
  "网络已断开，数据可能无法更新": "You are offline. Data may not update.",
  "正在连接后端服务...": "Connecting to the backend…", "后端服务未连接 — 请启动后端服务（port 8000）": "Backend disconnected — start the backend service (port 8000)",
  "重试": "Retry", "部分服务降级": "Some services are degraded", "后端已连接，部分服务状态异常": "Backend connected; some services are unavailable",
  "后端已连接，诊断信息暂不可用": "Backend connected; diagnostics are temporarily unavailable",
  "连接中": "Connecting", "已连接": "Connected", "诊断不可用": "Diagnostics unavailable", "部分异常": "Partially degraded", "未连接": "Disconnected",
  "技术分析": "Technical analysis", "资金流向": "Capital flows", "财务分析": "Financial analysis", "流派分析": "Investment perspectives", "信任度": "Reliability",
  "个股名称与报价尚未取得": "Stock name and quote unavailable", "正在获取…": "Loading…", "重新获取报价": "Retry quote",
  "当前报价接口未提供有效数据。分时、K线等模块独立加载；不把未知报价填成零。": "The quote service has not returned valid data. Charts load independently; missing quotes are not replaced with zero.",
  "AI 投资决策平台": "AI investment research platform",
  "语言偏好仅在本次页面生效，浏览器未允许保存。": "This language applies to the current page only; your browser did not allow saving the preference.",
};
export function translate(locale: Locale, text: string): string {
  return locale === "en" && Object.hasOwn(EN_MESSAGES, text) ? EN_MESSAGES[text] : text;
}
