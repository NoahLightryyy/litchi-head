"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseRawDaily } from "@/lib/raw-daily";
import { CandlestickChart } from "./candlestick-chart";

export function RawDailyChart({code}: {code:string}) {
  const query = useQuery({queryKey:["stocks",code,"raw-daily-display"],
    queryFn: async ({signal}) => parseRawDaily(await api.getRaw(`/stocks/${code}/kline-raw-display`, undefined,
      {signal:AbortSignal.any([signal,AbortSignal.timeout(15000)])}),code),
    retry:false, staleTime:300000});
  return <section className="space-y-3" aria-label="腾讯备用不复权日线">
    <p className="text-sm text-text-muted">原前复权日线不可用，以下使用腾讯备用历史日线。<strong>不复权 · 单源未交叉验证</strong>，除权除息可能形成价格跳空，不与前复权序列拼接。</p>
    {query.isPending ? <p role="status">正在获取备用日线…</p> : query.isError ? <p role="alert">备用日线也未取得有效数据，请稍后重试。</p> : <>
      <p className="text-sm">数据日期 {query.data.start} 至 {query.data.end} · {query.data.bars.length} 根日线 · 仅含已结束交易日</p>
      <CandlestickChart data={query.data.bars} />
    </>}
    <button disabled={query.isFetching} className="text-sm text-accent-blue" onClick={() => void query.refetch()}>刷新备用日线</button>
  </section>;
}
