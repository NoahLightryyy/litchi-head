import type { HotNewsItem, SectorItem } from "./types/market.ts";

const themes = [
  { name: "科技与制造", board: /半导体|芯片|电子|通信|算力|软件|机器人|机械|科技/, news: /半导体|芯片|算力|人工智能|机器人|制造业|科技/, path: "政策、企业投资若能变成设备采购和订单，才更可能支撑后续业绩；只有题材热度时，股价也可能很快回落。" },
  { name: "消费与居民需求", board: /消费|零售|食品|饮料|白酒|旅游|家电|汽车/, news: /消费|零售|补贴|以旧换新|居民收入|就业/, path: "居民收入、消费补贴和实际销量会影响需求；销量增长还要扣除促销成本，才能判断利润是否跟上。" },
  { name: "金融与资金环境", board: /银行|证券|保险|融资融券|金融/, news: /央行|利率|降息|降准|信贷|证券|融资/, path: "利率和信贷变化会影响资金成本与风险偏好；融资融券等宽泛概念资金靠前，并不等于券商或其中每家公司都能受益。" },
  { name: "能源与原材料", board: /煤炭|石油|有色|钢铁|化工|电力|能源/, news: /油价|煤炭|能源|电价|大宗|原材料|供需/, path: "商品价格、产量和下游需求会改变收入与成本；涨价可能利好上游，却挤压下游利润，需要分开看。" },
  { name: "建设与地产", board: /地产|建筑|建材|基建/, news: /房地产|楼市|基建|专项债|建筑/, path: "政策支持要转成项目开工、销售和回款，才会进入经营结果；股价可能先反应，业绩通常要晚一些。" },
];
export function summarizeSectors(items: SectorItem[], source: SectorItem["source"]) {
  const rows = items.filter(item => item.source === source);
  const flow = (item: SectorItem) => source === "sina" ? item.net_flow : item.fund_flow;
  const known = rows.filter(item => typeof flow(item) === "number" && Number.isFinite(flow(item)));
  const leaders = [...known].sort((a,b) => flow(b)! - flow(a)!).filter(item => flow(item)! > 0).slice(0,3);
  const positive = known.filter(item => flow(item)! > 0).length;
  const rising = rows.filter(item => item.change_pct > 0).length;
  const names = leaders.map(item => item.name).join("、");
  const fact = `${rows.length}个已取得板块中，${rising}个上涨；有资金数据的${known.length}个中，${positive}个净流入。${leaders.length ? `净流入靠前的是${names}。` : "当前没有取得净流入为正的领先板块。"}`;
  const divergent = leaders.filter(item => item.change_pct <= 0).map(item => item.name);
  const inference = !known.length ? "资金数据还没拿到，暂不能判断钱往哪里走。"
    : !leaders.length ? "这份榜单暂未显示明确的资金流入方向，先观察是否出现持续回流。"
    : divergent.length ? `${divergent.join("、")}虽有净流入，价格却没有同步上涨，买卖双方仍有分歧。后续要看资金能否持续、上涨板块是否增多。`
    : "靠前板块的价格和净流入同向，短线关注度较高；若后续资金转出或上涨范围缩小，这股热度可能难以持续。单次靠前不等于接下来还会涨。";
  const contexts = themes.filter(theme => leaders.some(item => theme.board.test(item.name))).slice(0,2);
  return { fact, inference, leaders, contexts };
}
export function sectorContextNews(items: HotNewsItem[], contexts: ReturnType<typeof summarizeSectors>["contexts"], now = Date.now()) {
  const seen = new Set<string>();
  return items.filter(item => {
    const date = item.date ? Date.parse(item.date) : NaN;
    let url: URL; try { url = new URL(item.url); } catch { return false; }
    if (!Number.isFinite(date) || date > now || now - date > 3 * 86400_000 || !["http:", "https:"].includes(url.protocol) || url.username || url.password
      || !contexts.some(theme => theme.news.test(item.title))) return false;
    const key = item.title.replace(/\s/g, ""); if (seen.has(key)) return false;
    seen.add(key); return true;
  }).sort((a,b) => Date.parse(b.date!) - Date.parse(a.date!)).slice(0,2);
}
