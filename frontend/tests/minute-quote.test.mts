import {test} from 'node:test';
import assert from 'node:assert/strict';
import {minuteQuoteRows} from '../lib/minute-quote.ts';
test('historical days never reuse latest quote previous close; extrema reset per day',()=>{
 const rows=minuteQuoteRows([
 {timestamp:'2026-09-29T09:30:00+08:00',close:20},
 {timestamp:'2026-09-30T09:30:00+08:00',close:10,cumulative_volume:0},
 {timestamp:'2026-09-30T09:31:00+08:00',close:11,cumulative_volume:100},
 ],{fetched_at:'2026-09-30T15:00:00+08:00',prev_close:10,source:'sina'});
 assert.equal(rows[0].percent,null);assert.equal(rows[0].volume,null);
 assert.equal(rows[1].high,10);assert.equal(rows[1].volume,0);
 assert.equal(rows[2].low,10);assert.equal(rows[2].amount,1);
 assert.ok(Math.abs(rows[2].percent!-10)<1e-9);
});
test('invalid prior close does not create infinity; sorted duplicate timestamps keep last point',()=>{
 const points=[{timestamp:'2026-09-30T09:31:00+08:00',close:11},{timestamp:'2026-09-30T09:30:00+08:00',close:10},{timestamp:'2026-09-30T09:31:00+08:00',close:12}];
 const rows=minuteQuoteRows(points,{fetched_at:'2026-09-30T15:00:00+08:00',prev_close:0});
 assert.equal(rows.length,2);assert.equal(rows[1].price,12);assert.equal(rows[1].percent,null);
});

import { minuteActivityRows } from '../lib/minute-quote.ts';
test('minute activity uses deltas, preserving zero and rejecting gaps and resets', () => {
 const rows = minuteActivityRows([
  { timestamp:'2026-09-30T09:30:00+08:00', close:10, cumulative_volume:100, cumulative_amount:1000 },
  { timestamp:'2026-09-30T09:31:00+08:00', close:11, cumulative_volume:120, cumulative_amount:1220 },
  { timestamp:'2026-09-30T09:32:00+08:00', close:11, cumulative_volume:120, cumulative_amount:1220 },
  { timestamp:'2026-09-30T09:34:00+08:00', close:11, cumulative_volume:150, cumulative_amount:1550 },
  { timestamp:'2026-09-30T09:35:00+08:00', close:10, cumulative_volume:10, cumulative_amount:100 },
 ]);
 assert.equal(rows[0].volume,null); assert.equal(rows[1].volume,20); assert.equal(rows[1].turnover,220);
 assert.equal(rows[2].volume,0); assert.equal(rows[3].volume,null); assert.equal(rows[4].volume,null);
});
test('provider zero sentinel for absent amount is not zero turnover', () => {
 const rows = minuteActivityRows([
 {timestamp:'2026-09-30T09:30:00+08:00',close:10,cumulative_volume:100,cumulative_amount:0},
 {timestamp:'2026-09-30T09:31:00+08:00',close:10,cumulative_volume:120,cumulative_amount:0},
 ]);
 assert.equal(rows[1].volume,20); assert.equal(rows[1].turnover,null);
});
