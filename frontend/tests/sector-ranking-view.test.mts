import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_VISIBLE_SECTOR_COUNT,
  hiddenSectorCount,
  visibleSectorItems,
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
  assert.deepEqual(visibleSectorItems(sectors, false), sectors.slice(0, 10));
  assert.equal(hiddenSectorCount(sectors, false), 5);
});

test("展开后显示全部板块且没有隐藏计数", () => {
  assert.deepEqual(visibleSectorItems(sectors, true), sectors);
  assert.equal(hiddenSectorCount(sectors, true), 0);
});
