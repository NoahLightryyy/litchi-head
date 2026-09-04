import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_VISIBLE_SECTOR_COUNT,
  hiddenSectorCount,
  visibleSectorItems,
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
}));

test("板块排行默认只显示前 10 个并折叠其余项", () => {
  assert.equal(DEFAULT_VISIBLE_SECTOR_COUNT, 10);
  assert.deepEqual(visibleSectorItems(sectors, 10), sectors.slice(0, 10));
  assert.equal(hiddenSectorCount(sectors, 10), 5);
});

test("最后一批只展示剩余项且没有隐藏计数", () => {
  assert.deepEqual(visibleSectorItems(sectors, 20), sectors);
  assert.equal(hiddenSectorCount(sectors, 20), 0);
});


test("千条数据逐批展开，不改变上游顺序、不一次渲染全部", () => {
  const large = Array.from({ length: 1000 }, (_, index) => ({ ...sectors[0], id: `BK${index}`, rank: index + 1 }));
  for (const count of [10, 20, 30]) {
    assert.equal(visibleSectorItems(large, count).length, count);
    assert.equal(hiddenSectorCount(large, count), 1000 - count);
    assert.deepEqual(visibleSectorItems(large, count), large.slice(0, count));
  }
  assert.equal(visibleSectorItems(large, 10).length, 10);
  assert.equal(large.length, 1000);
  assert.deepEqual(visibleSectorItems([], 20), []);
  assert.equal(hiddenSectorCount([], 20), 0);
});

test("涨跌条使用全榜同一比例，包含负值且全零不除零", () => {
  assert.equal(sectorChangeScale([{ ...sectors[0], change_pct: -12 }, { ...sectors[0], change_pct: 5 }]), 12);
  assert.equal(sectorChangeScale([{ ...sectors[0], change_pct: 0 }]), 1);
  assert.equal(sectorChangeScale([]), 1);
});
