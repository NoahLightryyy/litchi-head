import test from 'node:test';
import assert from 'node:assert/strict';
import {parseChainDraft} from '../lib/chain-draft.ts';
const fixture=()=>({schema_version:1,sector_code:'BK0917',sector_name:'测试',review_status:'ai_inferred_unverified',model:'test',cached:false,generated_at:'2026-10-18T16:00:00Z',graph:{map_kind:'industry_chain',scope:'假设',nodes:[{id:'a',label:'材料',role:'投入',verify:'成本'},{id:'b',label:'制造',role:'加工',verify:'产能'}],edges:[{source:'a',target:'b',explanation:'推断'}]}});
test('草图绑定标的并拒绝核验状态升级、错边与重复节点',()=>{
  assert.equal(parseChainDraft(fixture(),'BK0917','测试').graph.nodes.length,2);
  assert.throws(()=>parseChainDraft(fixture(),'BK1326','测试'));
  const status=fixture();status.review_status='verified';assert.throws(()=>parseChainDraft(status,'BK0917','测试'));
  const edge=fixture();edge.graph.edges[0].target='c';assert.throws(()=>parseChainDraft(edge,'BK0917','测试'));
  const nodes=fixture();nodes.graph.nodes[1].id='a';assert.throws(()=>parseChainDraft(nodes,'BK0917','测试'));
});
