/** Frozen backend contract d3c6673; decimals stay strings, unknown facts stay null. */
export const ACTION_LABELS = {buy: "买入", sell: "卖出", hold: "持有", watch: "关注", ignore: "忽略", skip: "跳过"} as const;
export type Action = keyof typeof ACTION_LABELS;
export interface ActionDraft {
  stock_code: string; session_id: string; action: string; local_time: string; offset: string;
  quantity: string; execution_price: string; currency: string; stated_reason: string;
}
export interface ActionCreate {
  client_action_id: string; session_id: string; stock_code: string; action: Action; occurred_at: string;
  quantity: string | null; execution_price: string | null; currency: string | null; stated_reason: string | null;
}
export interface ActionEvent extends ActionCreate {
  schema_version: "1"; event_id: string; user_id: string; recorded_at: string; source: "user_reported";
  ai_snapshot_status: "unverified"; limitations: string[];
}
export const validOwner = (v: string): boolean => /^[A-Za-z0-9._:-]{1,128}$/.test(v);
const positiveDecimal = (v: unknown): v is string => typeof v === "string" && /^\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v) && /[1-9]/.test(v.split(/[eE]/)[0]);
function decimalKey(v:string|null): string|null {
  if(v===null) return null;
  const [mantissa,exponent="0"]=v.split(/[eE]/),fraction=mantissa.split(".")[1] ?? "";
  const raw=mantissa.replace(".","").replace(/^0+/,""), digits=raw.replace(/0+$/,"");
  return `${digits}e${BigInt(exponent)-BigInt(fraction.length)+BigInt(raw.length-digits.length)}`;
}
const zonedTime = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d:\d\d)$/.test(v) && Number.isFinite(Date.parse(v));
function obj(v: unknown): Record<string, unknown> {
  if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error("账本接口格式不兼容");
  return v as Record<string, unknown>;
}
export function buildAction(d: ActionDraft, id: string): ActionCreate {
  if (!validOwner(id) || !/^\d{6}$/.test(d.stock_code) || !d.session_id.trim() || d.session_id.length > 128 || !Object.hasOwn(ACTION_LABELS, d.action)) throw new Error("请填写六位股票代码、记录批次和操作类型");
  const local = d.local_time.length === 16 ? `${d.local_time}:00` : d.local_time;
  const localDate = new Date(`${local}Z`);
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(local) || !Number.isFinite(localDate.getTime()) || localDate.toISOString().slice(0,19) !== local || !/^(Z|[+-](0\d|1[0-4]):[0-5]\d)$/.test(d.offset) || /[+-]14:(?!00)/.test(d.offset)) throw new Error("请填写有效的发生时间，并明确选择时区");
  for (const value of [d.quantity, d.execution_price]) if (value && (!/^\d+(\.\d+)?$/.test(value) || !positiveDecimal(value))) throw new Error("数量和成交价须为大于零的十进制数；未知请留空");
  if (!!d.execution_price !== !!d.currency || (d.currency && !/^[A-Z]{3}$/.test(d.currency))) throw new Error("填写成交价时须明确币种；未填价格时请留空币种");
  if (d.stated_reason.length > 1000) throw new Error("操作理由最多1000字");
  return {client_action_id:id, session_id:d.session_id.trim(), stock_code:d.stock_code, action:d.action as Action,
    occurred_at:`${local}${d.offset}`, quantity:d.quantity || null, execution_price:d.execution_price || null,
    currency:d.currency || null, stated_reason:d.stated_reason.trim() || null};
}
export function parseActionEvent(v: unknown, owner: string): ActionEvent {
  const e=obj(v);
  if (e.schema_version !== "1" || e.user_id !== owner || !validOwner(owner) || typeof e.event_id !== "string" || !e.event_id ||
      typeof e.client_action_id !== "string" || !validOwner(e.client_action_id) || typeof e.session_id !== "string" || !e.session_id ||
      typeof e.stock_code !== "string" || !/^\d{6}$/.test(e.stock_code) || typeof e.action !== "string" || !Object.hasOwn(ACTION_LABELS,e.action) ||
      !zonedTime(e.occurred_at) || !zonedTime(e.recorded_at) || e.source !== "user_reported" || e.ai_snapshot_status !== "unverified" ||
      !Array.isArray(e.limitations) || e.limitations.some(x=>typeof x!=="string") || !e.limitations.includes("ai_snapshot_not_verified") || !e.limitations.includes("user_identity_not_authenticated")) throw new Error("账本身份、时间或核验状态不兼容");
  for (const v of [e.quantity,e.execution_price]) if (v !== null && !positiveDecimal(v)) throw new Error("账本成交数值无效");
  if (e.execution_price === null ? e.currency !== null : typeof e.currency !== "string" || !/^[A-Z]{3}$/.test(e.currency)) throw new Error("账本币种不完整");
  if (e.stated_reason !== null && typeof e.stated_reason !== "string") throw new Error("账本理由格式无效");
  return e as unknown as ActionEvent;
}
export function parseActionList(v: unknown, owner: string, offset: number, limit: number) {
  const x=obj(v), m=obj(x.meta);
  if (!Array.isArray(x.data) || m.immutable !== true || m.offset !== offset || m.limit !== limit || !Number.isSafeInteger(m.total) || Number(m.total)<0 || x.data.length>limit || Number(m.total)<offset+x.data.length && x.data.length>0) throw new Error("账本分页格式不兼容");
  const events=x.data.map(e=>parseActionEvent(e,owner));
  if (new Set(events.map(e=>e.event_id)).size!==events.length) throw new Error("账本返回重复记录");
  return {events,total:Number(m.total)};
}
export function parseActionWrite(v: unknown, owner: string, expected: ActionCreate) {
  const x=obj(v),m=obj(x.meta), event=parseActionEvent(x.data,owner);
  if (m.immutable!==true || m.retry_mode!=="idempotent" || !["recorded","replayed"].includes(String(m.status)) ||
      event.client_action_id!==expected.client_action_id || event.stock_code!==expected.stock_code || event.session_id!==expected.session_id || event.action!==expected.action || Date.parse(event.occurred_at)!==Date.parse(expected.occurred_at) ||
      decimalKey(event.quantity)!==decimalKey(expected.quantity) || decimalKey(event.execution_price)!==decimalKey(expected.execution_price) || event.currency!==expected.currency || event.stated_reason!==expected.stated_reason) throw new Error("保存响应与本次记录不匹配，请核对后重试");
  return {event,replayed:m.status==="replayed"};
}
export function restoreAttempt(raw:string) {
  const x=obj(JSON.parse(raw)), d=obj(x.draft);
  if(typeof x.owner!=="string" || !validOwner(x.owner) || typeof x.clientId!=="string" ||
     ["stock_code","session_id","action","local_time","offset","quantity","execution_price","currency","stated_reason"].some(k=>typeof d[k]!=="string")) throw new Error("未确认提交的草稿已损坏，不能自动重发");
  const draft=d as unknown as ActionDraft;
  return {owner:x.owner,clientId:x.clientId,draft,payload:buildAction(draft,x.clientId)};
}
