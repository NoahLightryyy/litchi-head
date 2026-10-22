import test from 'node:test';
import assert from 'node:assert/strict';
import {capitalScenario} from '../lib/capital-scenarios.ts';
test('本金对照计算费用、风险及最低订单约束',()=>{
  const small=capitalScenario(10000,120,10), large=capitalScenario(500000,120,10);
  assert.equal(small.monthlyCost,220); assert.equal(small.loss,1900);
  assert.equal(small.themeExecutable,false); assert.equal(large.themeExecutable,true);
  assert.equal(large.commission,300); assert.equal(large.monthlyCost,420);
  assert.equal(capitalScenario(100000,0,0).monthlyCost,0);
});
test('拒绝非有限数、负数与非整数次数',()=>{
  for(const args of [[0,120,10],[NaN,120,10],[10000,-1,10],[10000,120,.5],[10000,Infinity,10]]) {
    assert.throws(()=>capitalScenario(args[0],args[1],args[2]));
  }
});
