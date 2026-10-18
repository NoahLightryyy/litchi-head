"use client";
import { useEffect, useRef, useState } from "react";
import { decimal, jobStorageKey, packageId, positiveDecimal, parseJob, parseSaved, parsePackage, parsePreview, researchFetch, ResearchApiError, type EvidencePackage, type Job, type Preview, type Subject } from "@/lib/policy-capital";

type Saved = { jobId?: string; key: string; budget: string };
const labels = { supported: "有证据支持", inferred: "推断待验证", insufficient: "证据不足", contradicted: "存在反证" };
const box = "rounded-lg border border-bg-tertiary p-4 space-y-3";
const button = "rounded border border-bg-tertiary px-3 py-2 text-accent-blue disabled:opacity-50";
const input = "w-full rounded border border-bg-tertiary bg-bg-primary p-2";
function ClaimList({ claims }: { claims: EvidencePackage["claims"] }) { return <ul className="space-y-3">{claims.map(c => <li key={c.id}><strong>{labels[c.assessment]}</strong> · {c.text}<p className="text-sm text-text-secondary">{c.limitations.join("；")}</p><p className="text-xs text-text-secondary">引用：{c.evidence_ids.join("、") || "无"}</p></li>)}</ul>; }
export function PolicyCapitalPanel(props: Subject & { name: string }) {
  return <Panel key={`${props.kind}:${props.code}`} {...props} />;
}
function Panel({kind,code,name}: Subject & {name:string}) {
  const [pkg,setPkg]=useState<EvidencePackage|null>(null), [loading,setLoading]=useState(true), [error,setError]=useState("");
  const [empty,setEmpty]=useState(false),[offline,setOffline]=useState(false),[revision,setRevision]=useState(0);
  const [budget,setBudget]=useState(""),[saved,setSaved]=useState<Saved|null>(null),[job,setJob]=useState<Job|null>(null),[busy,setBusy]=useState(false),[jobError,setJobError]=useState("");
  const [cash,setCash]=useState(""),[allocation,setAllocation]=useState(""),[price,setPrice]=useState(""),[quoteAt,setQuoteAt]=useState(""),[permission,setPermission]=useState(false),[market,setMarket]=useState<"SH"|"SZ"|"">("");
  const [preview,setPreview]=useState<Preview|null>(null),[previewBusy,setPreviewBusy]=useState(false),[previewError,setPreviewError]=useState("");
  const mutationAbort=useRef<AbortController|null>(null);
  useEffect(()=>{mutationAbort.current=new AbortController();return()=>mutationAbort.current?.abort();},[]);
  const storageKey=jobStorageKey({kind,code});
  useEffect(()=>{const sync=()=>setOffline(!navigator.onLine);sync();window.addEventListener("online",sync);window.addEventListener("offline",sync);return()=>{window.removeEventListener("online",sync);window.removeEventListener("offline",sync);};},[]);
  useEffect(()=>{
    const controller=new AbortController(); let alive=true;
    researchFetch(`/evidence/${encodeURIComponent(packageId({kind,code}))}`,{signal:controller.signal}).then(raw=>{if(alive)setPkg(parsePackage(raw,{kind,code}));}).catch(e=>{if(alive){if(e instanceof ResearchApiError && e.status===404)setEmpty(true);else setError(e instanceof Error?e.message:"证据读取失败");}}).finally(()=>{if(alive)setLoading(false);});
    const restoreTimer=setTimeout(()=>{if(!alive)return;try { const raw=localStorage.getItem(storageKey); if(raw){const s=parseSaved(raw);setSaved(s);setBudget(s.budget);} } catch {setJobError("浏览器无法恢复任务记录；提交前需启用本地存储，以免重复请求。");}},0);
    return()=>{alive=false;controller.abort();clearTimeout(restoreTimer);};
  },[kind,code,storageKey,revision]);
  useEffect(()=>{
    if(!pkg||!saved?.jobId||offline)return;
    let alive=true;let timer:ReturnType<typeof setTimeout>|undefined;const controller=new AbortController();const jobId=saved.jobId;
    const poll=async()=>{try{const raw=await researchFetch(`/jobs/${encodeURIComponent(jobId)}`,{signal:controller.signal});const next=parseJob(raw,pkg);if(next.job_id!==jobId)throw new Error("任务身份不一致，已停止更新。");if(!alive)return;setJob(next);setJobError("");if(next.status==="queued"||next.status==="running")timer=setTimeout(poll,3000);}catch(e){if(alive)setJobError(e instanceof Error?e.message:"任务读取失败，请手动刷新。");}};void poll();
    return()=>{alive=false;controller.abort();if(timer)clearTimeout(timer);};
  },[pkg,saved,offline,revision]);
  async function submit(newAttempt=false){
    if(!pkg||busy)return;setJobError("");
    if(!positiveDecimal(budget)){setJobError("请输入大于零的研究费用上限（元）。");return;}
    const intent:Saved=!newAttempt&&saved&&!saved.jobId?saved:{key:crypto.randomUUID(),budget};
    try{localStorage.setItem(storageKey,JSON.stringify(intent));}catch{setJobError("无法保存幂等记录，已阻止付费研究提交。请启用浏览器本地存储。");return;}
    setSaved(intent);setBusy(true);
    try{const raw=await researchFetch("/jobs",{method:"POST",signal:mutationAbort.current?.signal,body:JSON.stringify({idempotency_key:intent.key,evidence_package_id:pkg.package_id,subject_kind:kind,subject_id:code,max_cost_cny:intent.budget})});const next=parseJob(raw,pkg);const record={...intent,jobId:next.job_id};localStorage.setItem(storageKey,JSON.stringify(record));setSaved(record);setJob(next);}catch(e){setJobError(`${e instanceof Error?e.message:"提交失败"}。可用同一请求标识重新确认，不会自动新建任务。`);}finally{setBusy(false);}
  }
  async function calculate(){
    if(!pkg||kind==="sector")return;
    if(!market){setPreviewError("请明确选择该证券的交易市场。");return;}setPreviewBusy(true);setPreviewError("");setPreview(null);
    const money=(value:string)=>value.trim()?value.trim():null;
    if([cash,allocation,price].some(v=>v&&!decimal(v))){setPreviewError("金额请填写非负十进制数。");setPreviewBusy(false);return;}
    try{const raw=await researchFetch("/execution-preview",{method:"POST",signal:mutationAbort.current?.signal,body:JSON.stringify({evidence_package_id:pkg.package_id,instrument_kind:kind,symbol:code,market,side:"buy",order_type:"limit",cash_available_cny:money(cash),user_budget_cny:money(allocation),limit_price_cny:money(price),quote_at:quoteAt?new Date(quoteAt).toISOString():null,permission_confirmed:permission?true:null,rules:null,fees:null})});setPreview(parsePreview(raw,pkg.package_id));}catch(e){setPreviewError(e instanceof Error?e.message:"试算失败");}finally{setPreviewBusy(false);}
  }
  const active=job?.status==="queued"||job?.status==="running";
  return <section aria-label="政策与本金对照" className="rounded-xl border border-bg-tertiary bg-bg-secondary p-5 space-y-4">
    <header><h2 className="font-semibold">政策与本金对照</h2><p className="text-sm text-text-secondary">{name} · {code} · 当前标的专属证据与约束</p></header>
    {offline&&<p role="alert">当前离线。已暂停任务刷新；恢复网络后继续读取原任务，不会自动重新研究。</p>}
    {loading&&<p role="status">正在核验政策与标的证据…</p>}
    {error&&<p role="alert">{error}</p>}
    {empty&&<p>当前标的尚无已核验的证据包，不能把其他标的的政策结论套用到本页。</p>}
    {(error||empty)&&<button className={button} onClick={()=>{setError("");setEmpty(false);setLoading(true);setRevision(v=>v+1);}}>重新读取证据</button>}
    {pkg&&<><article className={box}><h3 className="font-semibold">央视报道与政策原文 · {pkg.status==="partial"?"证据仍有缺口":"声明范围已核验"}</h3><ClaimList claims={pkg.claims}/>
      {pkg.gaps.length>0&&<div><h4>待补证据</h4><ul className="list-disc pl-5">{pkg.gaps.map((g,i)=><li key={i}>{g}</li>)}</ul></div>}
      <details><summary className="cursor-pointer">查看原始来源、定位与日期（{pkg.evidence.length}）</summary><ul className="mt-3 space-y-4">{pkg.evidence.map(e=><li key={e.id}><a className="text-accent-blue underline" href={e.url} target="_blank" rel="noopener noreferrer">{e.title}</a><p className="text-sm">{e.id} · {e.publisher} · 发布 {e.published_date}</p><p className="text-sm">成文 {e.authored_date||"未载明"} · 生效 {e.effective_date||"未核实"} · 检索 {e.retrieved_at}</p><p className="text-sm">定位：{e.locator}</p><p>{e.summary}</p></li>)}</ul></details>
      {pkg.holdings.map((h,i)=><details key={i}><summary className="cursor-pointer">ETF {h.etf_symbol} 历史持仓 · 截至 {h.as_of}</summary><p>披露 {h.published_date} · {h.coverage==="top_ten"?"前十大持仓":h.coverage==="full_disclosure"?"完整披露":"部分持仓"}。历史数据不能代表当前持仓；未披露部分不能视为零。</p><ul>{h.holdings.map(x=><li key={x.symbol}>{x.symbol} · 净值占比 {x.nav_weight_pct}%</li>)}</ul></details>)}
    </article>
    <article className={box}><h3 className="font-semibold">AI政策研究</h3><p className="text-sm">以本页证据包研究传导条件、反证与缺口。费用为估算；不会自动发起付费任务。</p><label className="block">本次研究费用上限（元）<input className={input} inputMode="decimal" value={budget} onChange={e=>setBudget(e.target.value)} disabled={active||busy||!!saved&&!saved.jobId}/></label>
      {!active&&(!job||job.status!=="failed")&&<button className={button} disabled={busy||offline} onClick={()=>void submit(job?.status==="succeeded")}>{busy?"正在提交…":saved&&!saved.jobId?"用原请求确认提交结果":job?.status==="succeeded"?"重新研究（新的费用预算）":"开始研究"}</button>}
      {job&&<p role="status">任务状态：{{queued:"排队中",running:"研究中，可离开页面后回来查看",succeeded:"已完成",failed:"失败"}[job.status]}</p>}
      {job?.error&&<><p role="alert">{job.error.message}</p><button className={button} disabled={busy||offline||!job.error.retryable&&budget===saved?.budget} onClick={()=>void submit(true)}>{job.error.retryable?"手动重新研究（新任务）":"调整预算后重新研究"}</button></>}
      {jobError&&<p role="alert">{jobError}</p>}{saved?.jobId&&<button className={button} onClick={()=>setRevision(v=>v+1)}>刷新原任务</button>}
      {job?.result&&<div className="space-y-3"><ClaimList claims={job.result.claims}/>{([['成立条件',job.result.conditions],['反向证据与风险',job.result.counterarguments],['未解决缺口',job.result.gaps]] as const).map(([title,items])=><div key={title}><h4>{title}</h4><ul className="list-disc pl-5">{items.map((x,i)=><li key={i}>{x}</li>)}</ul></div>)}<p className="text-xs">模型 {job.result.model} · 提示版本 {job.result.prompt_version} · {job.result.generated_at} · 估算费用 ¥{job.result.estimated_cost_cny}</p></div>}
    </article></>}
    <article className={box}><h3 className="font-semibold">本金执行约束 · 单笔限价买入</h3>{kind==="sector"?<p>板块不能直接交易。请选择相关股票或ETF，再核验账户权限、实际费用与交易规则。</p>:<><p className="text-sm">仅检查单笔资金是否足够，不代表适合持有。本页尚未接入已验证的客户费率与交易规则，缺项时只展示阻断原因，不生成可买数量。</p>
      <div className="grid gap-3 sm:grid-cols-2">{([["可用现金（元）",cash,setCash],["本单预算（元）",allocation,setAllocation],["限价（元）",price,setPrice]] as const).map(([label,value,setter])=><label key={label}>{label}<input className={input} disabled={previewBusy} inputMode="decimal" value={value} onChange={e=>{setter(e.target.value);setPreview(null);}}/></label>)}<label>实际报价时间（本机时区）<input className={input} disabled={previewBusy} type="datetime-local" value={quoteAt} onChange={e=>{setQuoteAt(e.target.value);setPreview(null);}}/></label><label>交易市场<select disabled={previewBusy} className={input} value={market} onChange={e=>{setMarket(e.target.value as "SH"|"SZ"|"");setPreview(null);}}><option value="">请选择市场</option><option value="SH">上海</option><option value="SZ">深圳</option></select></label></div>
      <label className="block"><input disabled={previewBusy} type="checkbox" checked={permission} onChange={e=>{setPermission(e.target.checked);setPreview(null);}}/> 我声明已开通该品种交易权限（仍需服务端核验）</label><button className={button} disabled={!pkg||previewBusy||offline} onClick={()=>void calculate()}>{previewBusy?"正在核验…":"核验资金与缺项"}</button>{!pkg&&<p>需先取得当前标的证据包。</p>}{previewError&&<p role="alert">{previewError}</p>}{preview&&<div role="status">{preview.status==="blocked"?<><strong>暂不能给出可买数量</strong><ul className="list-disc pl-5">{preview.gaps.map((g,i)=><li key={i}>{g}</li>)}</ul></>:<p>单笔预算计算：{preview.quantity} 股／份 · 含费金额 ¥{preview.estimated_cost} · 现金余额 ¥{preview.remaining_cash}。仅为预算可负担性核验。</p>}</div>}</>}</article>
  </section>;
}
