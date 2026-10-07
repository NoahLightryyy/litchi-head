import test from 'node:test';
import assert from 'node:assert/strict';
import {parseIndexHistory} from '../lib/index-history.ts';
const sample=()=>({symbol:'sh000001',source:'tencent',price_unit:'points',volume_unit:'source_native',fetched_at:'2026-10-07T16:00:00+08:00',bars:[{date:'2026-09-30',open:3800,high:3850,low:3790,close:3842,volume:12}]});
test('index identity never aliases stock 000001 or another index',()=>{
 assert.equal(parseIndexHistory(sample(),'sh000001').bars[0].close,3842);
 assert.throws(()=>parseIndexHistory(sample(),'000001'));
 assert.throws(()=>parseIndexHistory(sample(),'sz399001'));
});
test('index units, invalid OHLC and duplicates fail validation',()=>{
 const wrong=sample();wrong.price_unit='CNY';assert.throws(()=>parseIndexHistory(wrong,'sh000001'));
 const bad=sample();bad.bars[0].high=1;assert.throws(()=>parseIndexHistory(bad,'sh000001'));
 const repeated=sample();repeated.bars.push(repeated.bars[0]);assert.throws(()=>parseIndexHistory(repeated,'sh000001'));
});
