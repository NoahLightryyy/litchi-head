import {api} from "./client.ts";
import {parseActionList,parseActionWrite,type ActionCreate} from "../user-action-ledger.ts";
export async function listActions(owner:string,offset:number,signal?:AbortSignal) {
  return parseActionList(await api.getRaw("/user/actions",{limit:"10",offset:String(offset)},
    {headers:{"X-User-Id":owner},signal:AbortSignal.any([...(signal?[signal]:[]),AbortSignal.timeout(15000)])}),owner,offset,10);
}
export async function saveAction(owner:string,payload:ActionCreate) {
  return parseActionWrite(await api.postRaw("/user/action",payload,{headers:{"X-User-Id":owner},signal:AbortSignal.timeout(15000)}),owner,payload);
}
