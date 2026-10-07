import test from 'node:test';
import assert from 'node:assert/strict';
import {parseRankingResult, type RankingResult} from '../lib/discovery-rankings.ts';
const fixture = (): RankingResult => ({metric:'main_net',period:'3',status:'ready',
 data:[{code:'300893',name:'松原',value:0,price:15,quoted_at:'2026-09-30T15:00:00+08:00'}],
 start_date:'2026-09-28',end_date:'2026-09-30',fetched_at:'2026-10-07T12:00:00Z',source:'eastmoney',scope:'沪深',unit:'CNY',cached:false,reason:''});
test('ranking rejects cross-period, wrong-unit and mismatched trading dates',()=>{
 assert.equal(parseRankingResult(fixture(),'main_net','3').data[0].value,0);
 assert.throws(()=>parseRankingResult(fixture(),'main_net','5'));
 const wrongUnit=fixture(); wrongUnit.unit='percent';
 assert.throws(()=>parseRankingResult(wrongUnit,'main_net','3'));
 const wrongDay=fixture(); wrongDay.data[0].quoted_at='2026-09-29T15:00:00+08:00';
 assert.throws(()=>parseRankingResult(wrongDay,'main_net','3'));
});
test('unavailable state cannot show substituted data and duplicates are rejected',()=>{
 const unavailable=fixture(); unavailable.status='unavailable';
 assert.throws(()=>parseRankingResult(unavailable,'main_net','3'));
 unavailable.data=[]; assert.equal(parseRankingResult(unavailable,'main_net','3').status,'unavailable');
 const duplicate=fixture(); duplicate.data.push(duplicate.data[0]);
 assert.throws(()=>parseRankingResult(duplicate,'main_net','3'));
});
