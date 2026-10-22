import assert from "node:assert/strict";
import test from "node:test";
import { addComparisonCompany, exactSearchBoard, matchingBoards, readSearchCompanies, shouldRetryScreening } from "../lib/screening.ts";
import type { SectorItem } from "../lib/types/market.ts";

test("临时断源只自动重试一次，不重试不存在或契约损坏", () => {
  for (const error of [{status: 0}, {status: 503}, {status: 500, message: "TimeoutError"}]) {
    assert.equal(shouldRetryScreening(0, error), true);
    assert.equal(shouldRetryScreening(1, error), false);
  }
  for (const error of [new Error("contract invalid"), {status: 404}, {status: 422},
    {status: 500, message: "unknown error"}, null]) assert.equal(shouldRetryScreening(0, error), false);
});

test("真实 StockInfo 不带 type 仍显示，保留代码前导零并去重", () => {
  assert.deepEqual(readSearchCompanies([{code: "001246", name: "宏源药业", market: "sz"},
    {code: "001246", name: "宏源药业"}]), [{code: "001246", name: "宏源药业"}]);
  assert.deepEqual(readSearchCompanies([]), []);
  for (const invalid of [null, {}, [{code: 1246, name: "x"}], [{code: "BK0012", name: "板块"}],
    [{code: "001246", name: " "}]]) assert.throws(() => readSearchCompanies(invalid));
});

test("行业词匹配多个板块，精确名称优先，不混合不同来源的板块分类", () => {
  const board = (id: string, name: string, source: "eastmoney" | "sina" = "eastmoney"): SectorItem =>
    ({id, name, source, category: "industry", as_of: null, snapshot_may_be_delayed: true,
      change_pct: 0, fund_flow: null, heat: "low", top_stocks: [], rank: 1});
  const boards = [board("BK0001", "半导体设备"), board("BK0002", "半导体"),
    board("BK0003", "银行"), board("new_dz", "半导体", "sina")];
  assert.deepEqual(matchingBoards(boards, " 半导体 ").map(b => b.id), ["BK0002", "BK0001"]);
  assert.deepEqual(matchingBoards(boards, "bk0003").map(b => b.name), ["银行"]);
  assert.equal(matchingBoards(boards, "不存在").length, 0);
  assert.equal(matchingBoards(boards, " ").length, 0);
  assert.equal(exactSearchBoard(boards, " 半导体 ")?.id, "BK0002");
  assert.equal(exactSearchBoard(boards, "bk0001")?.name, "半导体设备");
  assert.equal(exactSearchBoard(boards, "半导"), null);
  assert.equal(exactSearchBoard(boards, " "), null);
  assert.equal(exactSearchBoard([...boards, board("BK0004", "半导体")], "半导体"), null);
});

test("只有选定公司才能加入；跨搜索去重，最多四家，移除后可重新加入", () => {
  const companies = ["001246", "920344", "600000", "000001", "688001"].map(code => ({code, name: code}));
  let selected = companies.slice(0, 3);
  assert.equal(addComparisonCompany(selected, selected[0]), selected);
  assert.equal(addComparisonCompany(selected, {code: "半导体", name: "半导体"}), selected);
  selected = addComparisonCompany(selected, companies[3]);
  assert.equal(selected.length, 4);
  assert.equal(addComparisonCompany(selected, companies[4]), selected);
  selected = selected.filter(c => c.code !== companies[0].code);
  assert.equal(addComparisonCompany(selected, companies[4]).length, 4);
});
