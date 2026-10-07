import test from "node:test";
import assert from "node:assert/strict";
import { aggregateRawPeriod } from "../lib/raw-period.ts";
const bars = [
  {date:"2025-12-29",open:10,high:14,low:9,close:12,volume:100},
  {date:"2025-12-31",open:12,high:15,low:11,close:14,volume:200},
  {date:"2026-01-02",open:14,high:16,low:13,close:15,volume:300},
  {date:"2026-01-05",open:15,high:17,low:14,close:16,volume:400},
];
test("跨年周按周一分组，保留首开末收并汇总成交量",()=>{
  const result = aggregateRawPeriod(bars,"weekly");
  assert.deepEqual(result[0],{date:"2026-01-02",open:10,high:16,low:9,close:15,volume:600});
  assert.equal(result.length,2);
  assert.equal(bars[0].date,"2025-12-29");
});
test("自然月分组，不填造缺失日期，单根和空序列有效",()=>{
  const result = aggregateRawPeriod(bars,"monthly");
  assert.deepEqual(result.map(b=>[b.date,b.volume]),[["2025-12-31",300],["2026-01-05",700]]);
  assert.deepEqual(aggregateRawPeriod([],"monthly"),[]);
  assert.deepEqual(aggregateRawPeriod([bars[0]],"weekly"),[bars[0]]);
  assert.deepEqual(aggregateRawPeriod(bars,"daily"),bars);
});
