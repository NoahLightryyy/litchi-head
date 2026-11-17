import { volumeComparisonText, type TechnicalSupplement } from "@/lib/technical-supplement";

const number = (v: number | null | undefined, digits = 2) => v == null ? "—" : v.toFixed(digits);
const shares = (v: number | null) => v === null ? "—" : `${(v / 10000).toFixed(2)} 万股`;
const ratio = (v: number | null) => v === null ? "暂不能计算" : `${v.toFixed(2)} 倍（${v >= 1 ? "+" : ""}${((v - 1) * 100).toFixed(1)}%）`;
export function TechnicalSupplementView({ data }: { data: TechnicalSupplement }) {
  const a = data.adjusted, v = data.volume;
  const last = a.indicators.at(-1);
  return <div className="space-y-3 text-sm">
    <p className="text-text-secondary">资料日期：{v.data_date ?? a.data_end ?? "暂无"} · 仅已结束交易日，非实时行情</p>
    <div className="grid gap-3 md:grid-cols-2">
      <section className="rounded-md border border-bg-tertiary bg-bg-primary/40 p-4 space-y-2">
        <h4 className="font-semibold">{a.status === "available" ? "前复权数据已补齐" : "前复权数据暂未补齐"}</h4>
        {a.status === "available" ? <>
          <p className="text-text-secondary">腾讯 · {a.bar_count} 根日线<br />{a.data_start} 至 {a.data_end}</p>
          <p>已用同一前复权序列重算均线、RSI、MACD 和 KDJ，避免直接把分红除权后的价格跳空当成跌势。</p>
          <dl className="grid grid-cols-2 gap-2 font-mono">
            <div><dt>MA5</dt><dd>{number(last?.ma.ma5)}</dd></div>
            <div><dt>MA20</dt><dd>{number(last?.ma.ma20)}</dd></div>
            <div><dt>MA60</dt><dd>{number(last?.ma.ma60)}</dd></div>
            <div><dt>RSI14</dt><dd>{number(last?.rsi14)}</dd></div>
          </dl>
        </> : <p>{a.reason ?? "来源暂未返回可用前复权序列，其他资料不受影响。"}</p>}
      </section>
      <section className="rounded-md border border-bg-tertiary bg-bg-primary/40 p-4 space-y-2">
        <h4 className="font-semibold">{v.status === "available" ? "成交量数据已补齐" : v.status === "partial" ? "成交量已有，比较窗口尚不完整" : "成交量暂未取得"}</h4>
        {v.status !== "unavailable" ? <>
          <p>当日成交量：<strong>{shares(v.latest_shares)}</strong></p>
          <p>前5日平均：{shares(v.previous5_mean_shares)}<br />当日对比：{ratio(v.ratio_to_previous5)}</p>
          <p>前20日平均：{shares(v.previous20_mean_shares)}<br />当日对比：{ratio(v.ratio_to_previous20)}</p>
          <p className="rounded bg-bg-secondary p-2">{volumeComparisonText(v)}</p>
        </> : <p>未取得有效日成交量，不能判断是否放量。</p>}
      </section>
    </div>
    <p className="text-xs text-text-muted">这是新读取的资料，不会自动改写下方历史研究的结论。以后手动发起分析时会带入；补齐数据不等于买入条件已满足。</p>
    <details className="text-xs text-text-muted">
      <summary className="cursor-pointer">数据口径与来源详情</summary>
      <div className="mt-2 space-y-2 break-words"><p>{a.methodology}</p><p>{v.methodology}</p><p>{data.methodology}</p>
        <p>读取时间：{data.fetched_at} · 复权读取：{a.fetched_at ?? "未取得"} · 最多缓存5分钟</p>
        {Object.entries(data.diagnostics).map(([source, status]) => <p key={source}>{source}：{status}</p>)}
      </div>
    </details>
  </div>;
}
