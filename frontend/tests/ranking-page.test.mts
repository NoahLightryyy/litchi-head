import test from "node:test";
import assert from "node:assert/strict";
import { rankingPage } from "../lib/ranking-page.ts";

test("排行榜翻页保留全部记录和原始排序，尾页不足10条不丢失", () => {
  for (const count of [0, 1, 10, 11, 20, 21, 50]) {
    const original = Array.from({ length: count }, (_, index) => ({ code: String(600000 + index) }));
    const first = rankingPage(original, 1);
    const displayed = [];
    for (let page = 1; page <= first.pageCount; page++) {
      const view = rankingPage(original, page);
      assert.ok(view.items.length <= 10);
      displayed.push(...view.items);
    }
    assert.deepEqual(displayed, original);
  }
});

test("刷新后列表缩短会回到有效页，空榜不产生虚构记录", () => {
  const rows = Array.from({ length: 11 }, (_, index) => index);
  const view = rankingPage(rows, 5);
  assert.deepEqual(view.items, [10]);
  assert.equal(view.page, 2);
  assert.equal(view.start, 11);
  assert.equal(view.end, 11);
  assert.deepEqual(rankingPage([], 5), { items: [], page: 1, pageCount: 1, total: 0, start: 0, end: 0 });
});
