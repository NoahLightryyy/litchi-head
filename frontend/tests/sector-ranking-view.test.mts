import assert from "node:assert/strict";
import test from "node:test";

import {
  sectorPage,
  sectorChangeScale,
} from "../lib/sector-ranking-view.ts";
import type { SectorItem } from "../lib/types/market.ts";

const sectors: SectorItem[] = Array.from({ length: 15 }, (_, index) => ({
  id: `BK${index}`,
  name: `板块 ${index + 1}`,
  change_pct: 15 - index,
  fund_flow: null,
  heat: "medium",
  top_stocks: [],
  rank: index + 1,
  category: "industry",
  as_of: "2026-09-04T15:39:32+08:00",
  source: "eastmoney",
  snapshot_may_be_delayed: true,
}));

test("千条榜单按页切片，尾页及越界保留原排名", () => {
  const large = Array.from({length: 1000}, (_, i) => ({...sectors[0], id: `BK${i}`, rank: i + 1}));
  assert.deepEqual(sectorPage(large, "", 2).items.map(s => s.rank), [11,12,13,14,15,16,17,18,19,20]);
  assert.equal(sectorPage(large, "", 100).items[0].rank, 991);
  assert.equal(sectorPage(large, "", 101).page, 100);
  assert.equal(sectorPage(large, "", -1).page, 1);
  assert.equal(sectorPage(large, "", NaN).page, 1);
  assert.equal(sectorPage(sectors, "", 100).items.length, 5);
});

test("搜索覆盖全榜、忽略代码大小写和首尾空白，并夹紧缩小后的页码", () => {
  assert.equal(sectorPage(sectors, " bk14 ", 100).items[0].rank, 15);
  assert.equal(sectorPage(sectors, "板块 15", 2).page, 1);
  const empty = sectorPage(sectors, "没有这个板块", 100);
  assert.equal(empty.total, 0);
  assert.equal(empty.start, 0);
  assert.equal(empty.page, 1);
  assert.deepEqual(empty.items, []);
});

test("涨跌条使用全榜同一比例，包含负值且全零不除零", () => {
  assert.equal(sectorChangeScale([{ ...sectors[0], change_pct: -12 }, { ...sectors[0], change_pct: 5 }]), 12);
  assert.equal(sectorChangeScale([{ ...sectors[0], change_pct: 0 }]), 1);
  assert.equal(sectorChangeScale([]), 1);
});
