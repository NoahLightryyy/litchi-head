import type { HotNewsItem } from "./types/market.ts";

export type NewsWindow = "all" | "24h" | "7d";
export interface CleanNews {
  id: string;
  title: string;
  source: string;
  url: string | null;
  publishedAt: number | null;
}
export interface NewsTopic { label: string; ids: string[] }

// Aliases identify topics only. These rules never infer investment direction.
const TOPICS: [string, RegExp][] = [
  ["人工智能", /人工智能|\bAI\b|\bOpenAI\b|\bChatGPT\b|\bAnthropic\b|大模型|智能体|生成式/i],
  ["半导体", /半导体|芯片|晶圆|光刻/], ["算力", /算力|数据中心|服务器|液冷/],
  ["光通信", /光通信|光模块|光纤|\bCPO\b/i], ["机器人", /机器人|具身智能/],
  ["新能源车", /新能源汽车|新能源车|电动车|动力电池/], ["汽车", /汽车|整车|车企/],
  ["光伏", /光伏|太阳能|硅料/], ["风电", /风电|风力发电/], ["储能", /储能|固态电池/], ["电力", /电力|电网|电价|绿电/],
  ["医药", /医药|药物|药品|创新药|生物制药/], ["消费", /消费|零售|白酒|食品|旅游/],
  ["房地产", /房地产|楼市|房价|地产|住房/], ["金融", /银行|券商|保险|金融/],
  ["化工", /化工|化肥|农药/], ["有色金属", /有色|铜价|铝价|稀土|锂价/],
  ["黄金", /黄金|金价/], ["石油", /石油|原油|油价/], ["钢铁", /钢铁|钢材|铁矿/],
  ["农业", /农业|粮食|养殖|种业|猪价/], ["航运", /航运|运价|港口/],
  ["军工", /军工|国防|航空航天/], ["传媒", /传媒|游戏|电影|影视/],
  ["利率", /利率|降息|加息|降准/], ["汇率", /汇率|美元指数|(?:人民币|美元).{0,4}(?:走强|走弱|升值|贬值)/],
  ["贸易", /关税|贸易|出口|进口/], ["并购", /并购|重组|收购/],
  ["债券", /债券|美债|国债|公司债|发债|信贷/], ["通胀", /通胀|通缩|物价|\bCPI\b|\bPPI\b/i],
  ["软件", /软件/], ["地缘局势", /伊朗|美伊|俄乌|霍尔木兹|停火|战争/],
];
const FOCUS: [string, RegExp][] = [
  ["政策动态", /政策|监管|国务院|央行|财政|降息|加息|关税|改革/],
  ["供需变化", /供需|供应|需求|产能|订单|缺口|扩产|减产|库存|涨价|降价/],
  ["经营业绩", /业绩|营收|净利|利润|盈利|亏损|财报|毛利/],
  ["资金动向", /资金|净流入|净流出|融资|增持|减持|回购|分红/],
  ["技术进展", /技术|研发|量产|突破|发布|试验|临床|获批/],
  ["风险事件", /违约|诉讼|处罚|调查|冻结|退市|暴雷|风险/],
];
const STOP = new Set("当前 最新 今日 昨日 明日 近日 近期 最近 今年 明年 月份 市场 公司 企业 行业 板块 方面 表示 认为 预计 可能 未来 相关 持续 继续 进一步 已经 目前 其中 以及 进行 实现 推动 推进 提升 增加 增长 下降 下跌 上涨 下滑 回落 提高 加强 影响 消息 报道 记者 来源 数据 发布 中国 全国 全球 国内 国际 发展 情况 重要 主要 问题 工作 活动 有关 公告 快讯 用户 专享 本文 数据通 特别 关注 将会 有望 成为 出现 投资 投资者 经济 积极 加快 得到 带来 有限公司 股份 元 亿 万 倍".split(" "));

export function cleanText(value: unknown): string {
  if (typeof value !== "string") return "";
  const text = value.replace(/\s+/g, " ").trim();
  return /^(nan|null|undefined|none|n\/a|-)$/i.test(text) ? "" : text;
}
function publishedTime(value: unknown, now: number): number | null {
  const text = cleanText(value);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/i.test(text)) return null;
  const datePart = text.slice(0, 10);
  const calendar = new Date(`${datePart}T00:00:00Z`);
  if (!Number.isFinite(calendar.getTime()) || calendar.toISOString().slice(0, 10) !== datePart) return null;
  const time = Date.parse(text);
  return Number.isFinite(time) && time <= now ? time : null;
}
function safeUrl(value: unknown): string | null {
  try { const url = new URL(cleanText(value)); return /^https?:$/.test(url.protocol) ? url.href : null; }
  catch { return null; }
}
export function prepareNews(items: readonly HotNewsItem[], now: number) {
  const unique = new Map<string, CleanNews>();
  let invalid = 0, duplicates = 0;
  for (const item of items) {
    const title = cleanText(item?.title).replace(/【本文系[^】]*】/g, "").trim();
    const id = title.toLowerCase().replace(/[\p{P}\p{Z}\s]/gu, "");
    if (id.length < 2) { invalid++; continue; }
    const next = {id, title, source: cleanText(item.source) || "来源未提供", url: safeUrl(item.url), publishedAt: publishedTime(item.date, now)};
    const old = unique.get(id);
    if (old) {
      duplicates++;
      // Keep the earliest known publication of an identical headline; syndication isn't new heat.
      if (next.publishedAt !== null && (old.publishedAt === null || next.publishedAt < old.publishedAt)) unique.set(id, next);
    } else unique.set(id, next);
  }
  return {items: [...unique.values()], invalid, duplicates};
}
export function summarizeNews(items: readonly CleanNews[], window: NewsWindow, now: number) {
  const age = window === "24h" ? 86400000 : 7 * 86400000;
  const sample = items.filter(item => window === "all" || (item.publishedAt !== null && item.publishedAt <= now && now - item.publishedAt <= age));
  const topicIds = new Map<string, Set<string>>();
  const focusIds = new Map<string, Set<string>>();
  const segmenter = new Intl.Segmenter("zh-CN", {granularity: "word"});
  for (const item of sample) {
    const labels = new Set(TOPICS.filter(([, pattern]) => pattern.test(item.title)).map(([label]) => label));
    // Recurring entities not in the small finance dictionary can also enter the cloud.
    for (const part of segmenter.segment(item.title)) {
      const word = part.segment;
      // Short general verbs/nouns drown out actual themes; unknown candidates require
      // a recurring phrase/entity of at least three Chinese characters.
      if (!part.isWordLike || !/^[\p{Script=Han}]{3,8}$/u.test(word) || /[零一二三四五六七八九十百千万亿]+/.test(word) || STOP.has(word)) continue;
      if (TOPICS.some(([label, pattern]) => labels.has(label) && pattern.test(word))) continue;
      labels.add(word);
    }
    for (const label of labels) {
      if (!topicIds.has(label)) topicIds.set(label, new Set());
      topicIds.get(label)!.add(item.id);
    }
    for (const [label, pattern] of FOCUS) if (pattern.test(item.title)) {
      if (!focusIds.has(label)) focusIds.set(label, new Set());
      focusIds.get(label)!.add(item.id);
    }
  }
  const sorted = (map: Map<string, Set<string>>) => [...map].map(([label, ids]) => ({label, ids: [...ids]}))
    .sort((a, b) => b.ids.length - a.ids.length || a.label.localeCompare(b.label, "zh-CN"));
  const topics = sorted(topicIds).filter(x => x.ids.length >= 2 || TOPICS.some(([label]) => label === x.label)).slice(0, 18);
  return {sample, topics, focuses: sorted(focusIds), unknownDates: items.filter(x => x.publishedAt === null).length};
}

/** Preserve channel-specific reports; topic counting uses prepareNews separately. */
export function prepareNewsReports(items: readonly HotNewsItem[], now: number) {
  return items.flatMap((item, index) => prepareNews([item], now).items.map(report => ({
    ...report, reportKey: `${report.source}:${report.id}:${report.url ?? ""}:${index}`,
  })));
}
