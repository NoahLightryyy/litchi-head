import assert from "node:assert/strict";
import test from "node:test";
import { sectorHref, compareSinaSector } from "../lib/sector-navigation.ts";
import type { SectorItem } from "../lib/types/market.ts";

test("两种来源板块名称都进入站内，不冒用东财ID", () => {
  assert.equal(sectorHref({source: "sina", id: "sina:new_swzz"}), "/sector/sina/new_swzz");
  assert.equal(sectorHref({source: "eastmoney", id: "BK1629"}), "/sector/BK1629");
});
test("排名只比较同来源同分类，同值并列而非叠加", () => {
  const base: SectorItem = {source: "sina", id: "sina:new_a", name: "a", category: "industry",
    change_pct: 1, net_flow: 2, fund_flow: null, as_of: null, snapshot_may_be_delayed: true,
    heat: "medium", top_stocks: [], rank: 0};
  const result = compareSinaSector(base, [base, {...base, id: "sina:new_b"},
    {...base, id: "sina:new_c", change_pct: 2, net_flow: 1},
    {...base, category: "concept", change_pct: 100, net_flow: 100},
    {...base, source: "eastmoney", change_pct: 100, net_flow: 100}]);
  assert.deepEqual(result, {total: 3, changeRank: 2, flowRank: 1});
});
