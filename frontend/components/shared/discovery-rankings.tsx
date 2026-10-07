"use client";
import {useState, useRef} from "react";
import Link from "next/link";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/lib/api/client";
import {parseRankingResult, rankingPeriods, type RankingPeriod, type RankingMetric} from "@/lib/discovery-rankings";

export function DiscoveryRankings() {
  return <div className="space-y-5"><RankingPanel funds={false}/><RankingPanel funds/></div>;
}
function RankingPanel({funds}:{funds:boolean}) {
  const [period,setPeriod] = useState<RankingPeriod>("latest");
  const [metric,setMetric] = useState<RankingMetric>(funds ? "main_net" : "change");
  const title = funds ? "资金流入排行" : "个股涨幅排行";
  const forceRefresh = useRef(false);
  const query = useQuery({queryKey:["discovery","rankings",metric,period],
    queryFn: async ({signal}) => { const force = forceRefresh.current; forceRefresh.current = false; return parseRankingResult(await api.getRaw<unknown>(`/discovery/rankings?metric=${metric}&period=${period}&refresh=${force}`,undefined,{signal}),metric,period); },
    retry:false,staleTime:120000});
  const [refreshError,setRefreshError] = useState(false);
  const data = query.data;
  return <section aria-label={title} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{title}</h2>
      <button disabled={query.isFetching} onClick={() => { setRefreshError(false); forceRefresh.current = true; void query.refetch().then(result => setRefreshError(result.isError)); }} className="text-sm text-accent-blue disabled:opacity-50">{query.isFetching?"正在读取…":"刷新榜单"}</button>
    </div>
    <div className="flex flex-wrap gap-3">
      <label className="text-sm">统计周期<select aria-label={`${title}统计周期`} value={period} onChange={e=>{setPeriod(e.target.value as RankingPeriod);setRefreshError(false);}} className="ml-2 rounded border border-bg-tertiary bg-bg-primary p-2">
        {rankingPeriods.map(([value,label])=><option key={value} value={value}>{label}</option>)}
      </select></label>
      {funds && <label className="text-sm">资金口径<select aria-label="资金口径" value={metric} onChange={e=>{setMetric(e.target.value as RankingMetric);setRefreshError(false);}} className="ml-2 rounded border border-bg-tertiary bg-bg-primary p-2"><option value="main_net">主力净流入</option><option value="gross_in">总流入</option></select></label>}
    </div>
    <p className="text-xs leading-6 text-text-muted">按交易日统计，休市时以最近交易日为截止日。
      {funds ? "主力净流入采用来源的大单与超大单净额口径，负数为净流出；总流入单列，不与净额或成交额混用。" : "单日为来源当日涨幅；多日为来源区间涨幅，不是逐日百分比相加。新股比较基准可能不同。"}</p>
    {query.isPending ? <p role="status" className="py-4">正在读取所选周期榜单…</p> : (query.isError || refreshError) ? <p role="alert">所选榜单请求失败，请重试。</p> : data && <>
      <p className="text-sm">{data.start_date && data.end_date ? `统计交易日：${data.start_date} — ${data.end_date}` : "统计日期尚未取得"}{data.cached ? " · 缓存记录" : ""}</p>
      {data.reason && <p role="status" className="rounded-md bg-accent-gold/10 p-3 text-sm text-accent-gold">{data.reason}</p>}
      {data.status === "unavailable" ? <p className="text-sm text-text-muted">此周期暂无可展示的已核验榜单。可切换其他周期或稍后刷新；不会显示另一周期的数据。</p> : <>
        <p className="text-xs text-text-muted">{data.scope}。排序仅反映所示周期，不代表投资价值。金额为人民币。</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="text-text-muted"><th className="p-2">个股</th><th className="p-2 whitespace-nowrap">{metric==="change"?"区间涨幅":metric==="main_net"?"主力净流入（万元）":"总流入（万元）"}</th><th className="p-2">报价时间（北京时间）</th></tr></thead><tbody>
          {data.data.map(row=><tr key={row.code} className="border-t border-bg-tertiary"><td className="p-2"><Link href={`/stock/${row.code}`} className="text-accent-blue">{row.name}<span className="block text-xs text-text-muted">{row.code}</span></Link></td><td className={`p-2 font-number ${row.value>=0?"text-stock-up":"text-stock-down"}`}>{row.value>0?"+":""}{(metric==="change"?row.value:row.value/10000).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}{metric==="change"?"%":""}</td><td className="p-2 text-xs">{new Date(row.quoted_at).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false})}</td></tr>)}
        </tbody></table></div>
      </>}
    </>}
  </section>;
}
