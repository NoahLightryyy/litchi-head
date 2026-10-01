"use client";
import {useRef,useState} from "react";
import {useQuery,useQueryClient} from "@tanstack/react-query";
import {ApiError} from "@/lib/api/client";
import {listActions,saveAction} from "@/lib/api/user-actions";
import {ACTION_LABELS,buildAction,restoreAttempt,validOwner,type ActionDraft,type ActionCreate} from "@/lib/user-action-ledger";
const EMPTY:ActionDraft={stock_code:"",session_id:"",action:"",local_time:"",offset:"",quantity:"",execution_price:"",currency:"",stated_reason:""};
const PENDING_KEY="litchi.user-action.pending.v1";
type Attempt={owner:string;payload:ActionCreate;draft:ActionDraft;clientId:string};
const inputClass="mt-1 block w-full rounded border border-bg-tertiary bg-bg-primary p-2 disabled:opacity-60";

export function UserActionBoard() {
  const [ownerInput,setOwnerInput]=useState(""); const [owner,setOwner]=useState("");
  const [draft,setDraft]=useState<ActionDraft>(EMPTY); const [offset,setOffset]=useState(0);
  const [pending,setPending]=useState<Attempt|null>(null); const [saving,setSaving]=useState(false);
  const busy=useRef(false); const [message,setMessage]=useState(""); const [error,setError]=useState("");
  const qc=useQueryClient();
  const query=useQuery({queryKey:["user-actions",owner,offset],enabled:!!owner,
    queryFn:({signal})=>listActions(owner,offset,signal),retry:false,staleTime:30000});
  const change=(key:keyof ActionDraft,value:string)=>setDraft(v=>({...v,[key]:value}));
  async function submit() {
    if(busy.current) return;
    setError("");setMessage("");
    let attempt=pending;
    try {
      if(!owner) throw new Error("请先打开一个记录归属档案");
      if(!attempt) {
        if(sessionStorage.getItem(PENDING_KEY)) throw new Error("此标签页还有未确认提交，请先恢复并核对，避免重复记账");
        const clientId=crypto.randomUUID();
        attempt={owner,clientId,draft:{...draft},payload:buildAction(draft,clientId)};
        // Persist before sending. A reload can recover the same fact and idempotency key.
        sessionStorage.setItem(PENDING_KEY,JSON.stringify({owner,clientId,draft:attempt.draft}));
        setPending(attempt);
      }
      busy.current=true;setSaving(true);
      const result=await saveAction(attempt.owner,attempt.payload);
      sessionStorage.removeItem(PENDING_KEY);
      setPending(null);setDraft(EMPTY);setOffset(0);
      setMessage(result.replayed ? "已确认原记录，未重复记账。" : "操作事实已保存，可在下方查询。尚未计算账户盈亏。");
      await qc.invalidateQueries({queryKey:["user-actions",attempt.owner]});
    } catch(cause) {
      if(cause instanceof ApiError) {
        if(cause.status===422) {sessionStorage.removeItem(PENDING_KEY);setPending(null);}
        setError(cause.status===409 ? "此操作标识存在事实冲突，已停止提交。请先核对下方记录，不自动换标识重发。" : cause.status===422 ? "提交内容未通过账本校验。请核对字段；草稿已保留。" : "保存结果尚未确认。请使用“重试原提交”，保持相同标识和事实，避免重复记账。");
      } else setError(cause instanceof Error ? cause.message : "保存未成功确认，草稿已保留");
    } finally {busy.current=false;setSaving(false);}
  }
  function restore() {
    try {
      const raw=sessionStorage.getItem(PENDING_KEY);
      if(!raw) {setMessage("本标签页没有未确认提交。");return;}
      const attempt=restoreAttempt(raw);
      setOwnerInput(attempt.owner);setOwner(attempt.owner);setOffset(0);setDraft(attempt.draft);setPending(attempt);setError("");
      setMessage("已恢复未确认提交。请核对记录后，使用原标识重试。");
    } catch(cause) {setError(cause instanceof Error ? cause.message : "草稿恢复失败");}
  }
  return <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-4">
    <div><h1 className="text-xl font-semibold">我的实际操作</h1><p className="mt-2 text-sm text-text-muted">手动记录股票操作事实，保存到本机后端账本。这里只记录你填写的内容，暂不计算盈亏、费用或影子策略收益。</p></div>
    <form className="flex flex-wrap items-end gap-3" onSubmit={e=>{e.preventDefault();if(!validOwner(ownerInput.trim())){setError("归属标识请使用1–128位字母、数字、点、下划线、冒号或短横线");return;}setOwner(ownerInput.trim());setOffset(0);setMessage("");setError("");}}>
      <label className="text-sm">记录归属标识<input aria-label="记录归属标识" value={ownerInput} onChange={e=>setOwnerInput(e.target.value)} disabled={!!pending||saving} required maxLength={128} placeholder="例如 family-noah" className={inputClass}/></label>
      <button disabled={!!pending||saving} className="rounded bg-accent-blue px-4 py-2 text-white disabled:opacity-50">打开账本</button>
      <button type="button" disabled={saving} onClick={restore} className="text-sm text-accent-blue underline">恢复未确认提交</button>
    </form>
    <p className="text-xs text-text-muted">归属标识用于区分记录，当前尚未提供身份认证；请勿将服务开放给不可信网络。未确认提交暂存在当前标签页，刷新后可恢复；不会自动重发。</p>
    {owner && <>
      <form className="space-y-3 border-t border-bg-tertiary pt-4" onSubmit={e=>{e.preventDefault();void submit();}}>
        <fieldset disabled={saving||!!pending} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm">股票代码<input className={inputClass} required pattern="[0-9]{6}" maxLength={6} value={draft.stock_code} onChange={e=>change("stock_code",e.target.value)} /></label>
          <label className="text-sm">记录批次<input className={inputClass} required maxLength={128} placeholder="研究会话ID或自定手动批次" value={draft.session_id} onChange={e=>change("session_id",e.target.value)} /></label>
          <label className="text-sm">操作类型<select className={inputClass} required value={draft.action} onChange={e=>change("action",e.target.value)}><option value="">请选择</option>{Object.entries(ACTION_LABELS).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
          <label className="text-sm">发生时间<input className={inputClass} type="datetime-local" required step="1" value={draft.local_time} onChange={e=>change("local_time",e.target.value)}/></label>
          <label className="text-sm">上述时间的时区<select className={inputClass} required value={draft.offset} onChange={e=>change("offset",e.target.value)}><option value="">明确选择时区</option><option value="+08:00">中国标准时间 UTC+08:00</option><option value="+02:00">法国夏令时间 UTC+02:00</option><option value="+01:00">法国冬令时间 UTC+01:00</option><option value="Z">UTC</option></select></label>
          <label className="text-sm">成交数量（可选）<input className={inputClass} inputMode="decimal" value={draft.quantity} onChange={e=>change("quantity",e.target.value)} /></label>
          <label className="text-sm">成交价格（可选）<input className={inputClass} inputMode="decimal" value={draft.execution_price} onChange={e=>change("execution_price",e.target.value)} /></label>
          <label className="text-sm">价格币种<input className={inputClass} maxLength={3} pattern="[A-Z]{3}" placeholder="填价格时必填，如 CNY" value={draft.currency} onChange={e=>change("currency",e.target.value.toUpperCase())} /></label>
          <label className="text-sm sm:col-span-2 lg:col-span-3">操作理由（可选）<textarea className={inputClass} rows={2} maxLength={1000} value={draft.stated_reason} onChange={e=>change("stated_reason",e.target.value)}/></label>
        </fieldset>
        <p className="text-xs text-text-muted">未知数量和价格请留空。记录提交后不可修改；研究批次引用尚未核验，不代表 AI 建议已验证。</p>
        <button disabled={saving} className="rounded bg-accent-blue px-4 py-2 text-white disabled:opacity-50">{saving?"正在确认保存…":pending?"重试原提交":"保存操作事实"}</button>
      </form>
      <div className="flex justify-between border-t border-bg-tertiary pt-4"><h2 className="font-semibold">已记录操作 · {owner}</h2><button disabled={query.isFetching} className="text-sm text-accent-blue" onClick={()=>void query.refetch()}>刷新记录</button></div>
      {query.isPending ? <p role="status">正在读取账本…</p> : query.isError ? <p role="alert" className="text-accent-red">账本读取失败，无法确认是否存在记录。请重试。</p> : !query.data.events.length ? <p>此归属标识下暂无记录。</p> : <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm"><thead><tr>{["发生时间（原时区）","股票 / 操作","成交事实","批次 / 理由"].map(h=><th key={h} className="p-2 text-left">{h}</th>)}</tr></thead><tbody>{query.data.events.map(v=><tr key={v.event_id} className="border-t border-bg-tertiary"><td className="p-2 align-top">{v.occurred_at.replace("T"," ")}<p className="mt-1 text-xs text-text-muted">手动填报 · AI 引用未核验</p></td><td className="p-2 align-top">{v.stock_code}<p>{ACTION_LABELS[v.action]}</p></td><td className="p-2 align-top">数量：{v.quantity??"未填写"}<p>价格：{v.execution_price===null?"未填写":`${v.execution_price} ${v.currency}`}</p></td><td className="p-2 align-top max-w-xs break-words">{v.session_id}<p>{v.stated_reason??"未填写理由"}</p><details className="mt-1 text-xs text-text-muted"><summary>记录凭据</summary><p>{v.event_id}</p><p>入账 {v.recorded_at}</p></details></td></tr>)}</tbody></table></div>}
      {query.data && !query.isError && <nav aria-label="操作记录分页" className="flex flex-wrap items-center gap-3 text-sm"><button disabled={offset===0||query.isFetching} onClick={()=>setOffset(0)}>首页</button><button disabled={offset===0||query.isFetching} onClick={()=>setOffset(v=>Math.max(0,v-10))}>上一页</button><span>共 {query.data.total} 条 · 第 {Math.floor(offset/10)+1} / {Math.max(1,Math.ceil(query.data.total/10))} 页</span><button disabled={offset+10>=query.data.total||query.isFetching} onClick={()=>setOffset(v=>v+10)}>下一页</button><button disabled={offset+10>=query.data.total||query.isFetching} onClick={()=>setOffset(Math.max(0,Math.ceil(query.data.total/10)-1)*10)}>尾页</button></nav>}
    </>}
    {error && <p role="alert" className="rounded border border-accent-red/30 p-3 text-sm text-accent-red">{error}</p>}
    {message && <p role="status" className="text-sm text-accent-blue">{message}</p>}
  </section>;
}
