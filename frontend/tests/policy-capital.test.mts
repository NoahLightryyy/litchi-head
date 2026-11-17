import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePackage,parseJob,parsePreview,jobStorageKey,decimal,parseSaved,positiveDecimal,canSubmitResearch} from '../lib/policy-capital.ts';
const subject={kind:'stock' as const,code:'688012'};
const pkg={schema_version:1 as const,package_id:'v1-stock-688012',subject_kind:'stock' as const,subject_id:'688012',status:'partial' as const,evidence:[],claims:[],gaps:['缺口'],holdings:[]};
test('identity is isolated including job storage',()=>{assert.throws(()=>parsePackage(pkg,{kind:'etf',code:'688012'}));assert.notEqual(jobStorageKey(subject),jobStorageKey({kind:'etf',code:'688012'}));});
test('dangling citations cannot become evidence',()=>{assert.throws(()=>parsePackage({...pkg,claims:[{id:'1',text:'结论',assessment:'supported',evidence_ids:['missing'],limitations:[]}]},subject));});
test('blocked response never exposes precise amount',()=>{assert.throws(()=>parsePreview({status:'blocked',evidence_package_id:pkg.package_id,quantity:100,estimated_cost:null,remaining_cash:null,gaps:['缺费率']},pkg.package_id));});
test('monetary values require decimal strings',()=>{assert.equal(decimal(1.2),false); assert.equal(decimal('1.20'),true);assert.throws(()=>parsePreview({status:'ready',evidence_package_id:pkg.package_id,quantity:100,estimated_cost:12,remaining_cash:'0',gaps:[]},pkg.package_id));});
test('job terminal state and result identity checked',()=>{assert.throws(()=>parseJob({job_id:'1',status:'succeeded',result:null,error:null},pkg));assert.throws(()=>parseJob({job_id:'1',status:'succeeded',result:{evidence_package_id:'other'},error:null},pkg));assert.equal(parseJob({job_id:'1',status:'running',result:null,error:null},pkg).status,'running');});

test('decimal exponents and recovery records follow contract',()=>{assert.equal(decimal('0E-8'),true);assert.equal(decimal('1E+2'),true);assert.equal(positiveDecimal('0E+2'),false);assert.equal(positiveDecimal('0.01E-2'),true);assert.throws(()=>parseSaved('{"key":"short","budget":"1"}'));assert.equal(parseSaved('{"key":"abcdefgh","budget":"1","jobId":"a"}').jobId,'a');});
test('holdings refuse duplicate symbols and totals above 100',()=>{const evidence={id:'e',title:'title',url:'https://example.org',publisher:'p',published_date:'2025-01-01',authored_date:null,effective_date:null,locator:'p1',summary:'s',retrieved_at:'2025-01-01T00:00:00Z'};const h={etf_symbol:'512480',as_of:'2024-12-31',published_date:'2025-01-01',coverage:'top_ten',evidence_id:'e',holdings:[{symbol:'688012',nav_weight_pct:'60'},{symbol:'688012',nav_weight_pct:'1'}]};assert.throws(()=>parsePackage({...pkg,evidence:[evidence],holdings:[h]},subject));assert.throws(()=>parsePackage({...pkg,evidence:[evidence],holdings:[{...h,holdings:[{symbol:'688012',nav_weight_pct:'60'},{symbol:'688013',nav_weight_pct:'50'}]}]},subject));});
test('unknown errors and retry contradictions rejected',()=>{assert.throws(()=>parseJob({job_id:'a',status:'failed',result:null,error:{code:'OTHER',message:'x',retryable:true}},pkg));assert.throws(()=>parseJob({job_id:'a',status:'failed',result:null,error:{code:'BUDGET_EXCEEDED',message:'x',retryable:true}},pkg));});

test('restoring or unknown persisted job can never authorize new billing',()=>{assert.equal(canSubmitResearch(false,null,null),false);assert.equal(canSubmitResearch(true,{jobId:'original'},null),false);assert.equal(canSubmitResearch(true,{jobId:'original'},{job_id:'original',status:'running',result:null,error:null}),false);assert.equal(canSubmitResearch(true,{jobId:'original'},{job_id:'other',status:'failed',result:null,error:{code:'INTERRUPTED',message:'restart',retryable:true}}),false);assert.equal(canSubmitResearch(true,{jobId:'original'},{job_id:'original',status:'failed',result:null,error:{code:'INTERRUPTED',message:'restart',retryable:true}}),true);assert.equal(canSubmitResearch(true,{},null),true);});

test('示例标的清单与后端证据包一致，入口指向各自详情页', async () => {
  const { readFileSync } = await import('node:fs');
  const { VERIFIED_SAMPLE_SUBJECTS, sampleSubjectHref, sampleSubjectLabel, packageId } = await import('../lib/policy-capital.ts');
  const packages = JSON.parse(readFileSync(new URL('../../backend/policy_evidence_data/packages.json', import.meta.url), 'utf8'));
  assert.deepEqual(VERIFIED_SAMPLE_SUBJECTS.map(packageId).sort(), Object.keys(packages).sort());
  assert.deepEqual(VERIFIED_SAMPLE_SUBJECTS.map(sampleSubjectHref), ['/sector/BK0917', '/stock/688012', '/etf/512480']);
  assert.deepEqual(VERIFIED_SAMPLE_SUBJECTS.map(sampleSubjectLabel), ['板块 BK0917', '股票 688012', 'ETF 512480']);
});
