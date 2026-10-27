import test from "node:test";
import assert from "node:assert/strict";
import { summarizeSectors, sectorContextNews } from "../lib/sector-summary.ts";
import type { SectorItem } from "../lib/types/market.ts";
const board = (name: string, net_flow: number|null, change_pct: number, source: SectorItem['source'] = "sina"): SectorItem => ({ name, id: name, source, category: 'concept', net_flow, fund_flow: null, change_pct, as_of: null, snapshot_may_be_delayed: false, heat: 'low', top_stocks: [], rank: 1 });
test("按当前筛选的完整榜单统计，不求和重叠资金、不用别的来源补数", () => {
  const value = summarizeSectors([board('半导体', 20, 2), board('通信', 10, -1), board('软件', null, 1), board('银行', -3, -2), board('汽车', 999, 2, 'eastmoney')], 'sina');
  assert.match(value.fact, /4个已取得板块中，2个上涨/); assert.match(value.fact, /3个中，2个净流入/);
  assert.deepEqual(value.leaders.map(x=>x.name), ['半导体','通信']); assert.match(value.inference, /价格却没有同步上涨/);
  assert.equal(value.contexts[0].name, '科技与制造');
});
test("零、缺失与流出不编造资金方向", () => {
  assert.match(summarizeSectors([board('半导体',null,2)],'sina').inference,/还没拿到/);
  assert.equal(summarizeSectors([board('半导体',0,2),board('通信',-2,-1)],'sina').leaders.length,0);
});
test("近期背景须有真实日期安全链接且主题相关，重复和未来报道不算", () => {
  const contexts = summarizeSectors([board('半导体',1,2)],'sina').contexts;
  const item = { title:'半导体投资消息', date:'2026-10-26T12:00:00+08:00', source:'财联社', url:'https://example.com/1' };
  const rows = sectorContextNews([item, {...item,url:'https://example.com/2'}, {...item,title:'白酒消息'}, {...item,title:'芯片未来',date:'2026-11-01'}, {...item,title:'芯片旧闻',date:'2020-01-01'}, {...item,title:'芯片无日期',date:null}, {...item,title:'芯片坏链接',url:'javascript:alert(1)'}], contexts,Date.parse('2026-10-27T06:00:00+08:00'));
  assert.deepEqual(rows,[item]);
});
