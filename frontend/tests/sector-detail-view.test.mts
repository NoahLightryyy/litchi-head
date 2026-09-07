import assert from "node:assert/strict";
import test from "node:test";

import { resolveSectorDetailViewMode } from "../lib/sector-detail-view.ts";
import type { SectorDetail } from "../lib/types/market.ts";

const sector: SectorDetail = {
  id: "BK001",
  name: "示例板块",
  change_pct: 1.2,
  fund_flow: null,
  heat: "medium",
  chain_map: [],
  ai_analysis: "",
  stocks: [],
};

test("板块详情加载期间只显示 loading", () => {
  assert.equal(
    resolveSectorDetailViewMode({ sector: undefined, isLoading: true, isError: false }),
    "loading",
  );
});

test("板块详情请求失败与空结果不会混为一谈", () => {
  assert.equal(
    resolveSectorDetailViewMode({ sector: undefined, isLoading: false, isError: true }),
    "error",
  );
  assert.equal(
    resolveSectorDetailViewMode({ sector: undefined, isLoading: false, isError: false }),
    "empty",
  );
});

test("板块详情存在时显示真实数据", () => {
  assert.equal(
    resolveSectorDetailViewMode({ sector, isLoading: false, isError: false }),
    "data",
  );
});

test("后台刷新失败保留已有详情，由提示披露刷新失败", () => {
  assert.equal(resolveSectorDetailViewMode({ sector, isLoading: false, isError: true }), "data");
});
