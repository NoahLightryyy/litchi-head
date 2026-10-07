import {test} from 'node:test';
import assert from 'node:assert/strict';
import {candleChange,historyRange,historyViewport} from '../lib/chart-navigation.ts';
test('history slider spans oldest to latest without changing window size',()=>{
  assert.deepEqual(historyRange(156,0,60),{from:-0.5,to:59.5});
  assert.deepEqual(historyRange(156,999,60),{from:95.5,to:155.5});
  assert.deepEqual(historyViewport(156,historyRange(156,42,60)),{size:60,max:96,start:42,end:101});
});
test('full history and short datasets do not scroll outside returned data',()=>{
  assert.deepEqual(historyViewport(10,historyRange(10,0,60)),{size:10,max:0,start:0,end:9});
  assert.equal(historyViewport(156,{from:-10,to:180}).max,0);
  assert.equal(historyViewport(156,{from:-1,to:59}).size,60);
  assert.equal(historyViewport(156,{from:0.000000001,to:154.999999999}).size,156);
  assert.deepEqual(historyViewport(156,{from:0,to:155}),{size:156,max:0,start:0,end:155});
});
test('change uses previous close, not current open, and retains unknowns',()=>{
  const change=candleChange([12.61,15.13],1)!;
  assert.ok(Math.abs(change.percent-19.98413957)<0.000001);
  assert.ok(Math.abs(change.amount-2.52)<1e-10);
  assert.equal(candleChange([12.61],0),null);
  assert.equal(candleChange([0,10],1),null);
  assert.equal(candleChange([NaN,10],1),null);
  assert.equal(candleChange([10,10],1)?.percent,0);
  assert.equal(candleChange([10,9],1)?.amount,-1);
});
