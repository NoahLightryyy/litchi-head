import test from 'node:test';
import assert from 'node:assert/strict';
import {QueryClient, QueryObserver, onlineManager} from '@tanstack/react-query';
import {chainDraftRecovery, retryChainDraft} from '../lib/chain-draft-query.ts';

const tick=()=>new Promise(r=>setTimeout(r,10));
test('失败缓存返回页面会恢复，成功缓存不会再次生成',async()=>{
  const client=new QueryClient({defaultOptions:{queries:{gcTime:Infinity}}});
  const key=['chain-draft','BK0917','半导体概念'];let calls=0;
  try {
    await assert.rejects(client.fetchQuery({queryKey:key,retry:false,queryFn:async()=>{throw new Error('deployment unavailable');}}));
    const options={queryKey:key,...chainDraftRecovery,queryFn:async()=>{calls++;return 'saved graph';}};
    const first=new QueryObserver(client,options);const stop=first.subscribe(()=>{});
    await tick();assert.equal(first.getCurrentResult().data,'saved graph');stop();
    const second=new QueryObserver(client,options);const stop2=second.subscribe(()=>{});
    await tick();assert.equal(calls,1);assert.equal(second.getCurrentResult().data,'saved graph');stop2();
  } finally {client.clear();}
});
test('繁忙自动恢复，参数和结构错误不循环，重试次数有界',async()=>{
  assert.equal(retryChainDraft(5,{code:'CHAIN_DRAFT_BUSY'}),true);
  assert.equal(retryChainDraft(6,{code:'CHAIN_DRAFT_BUSY'}),false);
  assert.equal(retryChainDraft(2,{code:'NETWORK_ERROR'}),false);
  assert.equal(retryChainDraft(1,{code:'CHAIN_DRAFT_TIMEOUT'}),false);
  assert.equal(retryChainDraft(0,{status:422}),false);
  assert.equal(retryChainDraft(0,new Error('invalid graph')),false);
  const client=new QueryClient();let calls=0;
  try {
    const value=await client.fetchQuery({queryKey:['busy'],...chainDraftRecovery,retryDelay:0,queryFn:async()=>{
      calls++;if(calls===1)throw {code:'CHAIN_DRAFT_BUSY'};return 'persisted';
    }});
    assert.equal(value,'persisted');assert.equal(calls,2);
  } finally {client.clear();}
});

test('离线首次访问恢复联网后自动绘图',async()=>{
  const client=new QueryClient();client.mount();onlineManager.setOnline(false);let calls=0;
  const observer=new QueryObserver(client,{queryKey:['offline'],...chainDraftRecovery,queryFn:async()=>{calls++;return 'graph';}});
  const stop=observer.subscribe(()=>{});
  try {
    await tick();assert.equal(calls,0);assert.equal(observer.getCurrentResult().fetchStatus,'paused');
    onlineManager.setOnline(true);await tick();assert.equal(calls,1);assert.equal(observer.getCurrentResult().data,'graph');
  } finally {stop();client.unmount();client.clear();onlineManager.setOnline(true);}
});
