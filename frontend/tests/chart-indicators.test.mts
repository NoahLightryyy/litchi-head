import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chartIndicators, type CandleInput} from '../lib/chart-indicators.ts';
function rows(count:number):CandleInput[]{return Array.from({length:count},(_,i)=>({date:`2026-01-${i+1}`,open:10,high:10,low:10,close:10,volume:100}));}
test('flat series stays neutral; warmup is missing rather than zero',()=>{
 const r=chartIndicators(rows(60));
 assert.equal(r.ma60[58],null);assert.equal(r.ma60[59],10);
 assert.equal(r.rsi[13],null);assert.equal(r.rsi[14],50);
 assert.equal(r.dea[32],null);assert.equal(r.dea[33],0);
 assert.equal(r.histogram[59],0);assert.equal(r.k[7],null);assert.equal(r.k[8],50);
 assert.equal(r.upper[59],10);assert.equal(r.lower[59],10);
});
test('KDJ uses full nine bar seed and J is not clipped',()=>{
 const r=chartIndicators(rows(12).map(row=>({...row,low:0})));
 assert.ok(Math.abs(r.k[8]!-200/3)<1e-10);
 assert.ok(Math.abs(r.d[8]!-500/9)<1e-10);
 assert.ok(r.j[11]!>100);
});
test('rising and falling prices preserve RSI and MA direction',()=>{
 const rising=chartIndicators(rows(70).map((row,i)=>({...row,close:i+1,high:i+1,low:i+1})));
 const falling=chartIndicators(rows(70).map((row,i)=>({...row,close:100-i,high:100-i,low:100-i})));
 assert.equal(rising.rsi[69],100);assert.equal(falling.rsi[69],0);
 assert.equal(rising.ma5[69],68);assert.equal(rising.ma60[69],40.5);
 assert.ok(rising.dif[69]!>0);assert.ok(falling.dif[69]!<0);
 assert.deepEqual(chartIndicators([]).rsi,[]);
});
