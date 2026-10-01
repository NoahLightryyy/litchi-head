import test from "node:test";
import assert from "node:assert/strict";
import { latestFinancial, checkedValuation, displayMetric } from "../lib/sector-fundamentals.ts";
const row = (day: string) => ({stock_code:"300199",report_date:day,roe:-1,gross_margin:0,revenue_growth:2,net_profit_growth:-3,operating_cf_per_share:1,debt_ratio:70});
test("乱序财报取实际最新一期，不变更源数组", () => {
  const rows=[row("2024-03-31"),row("2026-06-30"),row("2025-12-31")];
  assert.equal(latestFinancial(rows,"300199")?.report_date,"2026-06-30");
  assert.equal(rows[0].report_date,"2024-03-31");
  assert.equal(latestFinancial([],"300199"),null);
});
test("拒绝串股、无效日期和非有限指标", () => {
  for(const rows of [[row("2026-02-30")],[{...row("2026-06-30"),stock_code:"000001"}], [{...row("2026-06-30"),roe:NaN}]]) assert.throws(()=>latestFinancial(rows,"300199"));
});
test("缺失估值不补零，零值不伪装有效", () => {
  assert.equal(checkedValuation(null,"300199"),null);
  assert.equal(displayMetric(undefined),"—");
  assert.equal(displayMetric(0),"0（待核验）");
  assert.equal(displayMetric(-1.5,"%"),"-1.50%");
  assert.throws(()=>checkedValuation({stock_code:"000001",report_date:"2026-06-30",pe:1,pb:1,ps:1,market_cap:10},"300199"));
});
