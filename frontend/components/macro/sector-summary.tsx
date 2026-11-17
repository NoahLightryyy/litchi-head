import type { HotNewsItem, SectorItem } from "@/lib/types/market";
import { sectorTimeRange } from "@/lib/sector-availability";
import { sectorContextNews, summarizeSectors } from "@/lib/sector-summary";

export function SectorSummary({ items, source, historical, news = [] }: { items: SectorItem[]; source: SectorItem["source"]; historical: boolean; news?: HotNewsItem[] }) {
  if (!items.length) return null;
  const summary = summarizeSectors(items, source);
  const background = sectorContextNews(news, summary.contexts);
  return <aside aria-label="榜单怎么看" className="rounded-lg border border-accent-blue/20 bg-accent-blue/5 p-4 space-y-3 text-sm leading-6">
    <h4 className="font-semibold">榜单怎么看</h4>
    <p>{historical ? "按保留的历史榜单看：" : "这份榜单显示："}{summary.fact}</p>
    <p><strong className="text-accent-blue">可能意味着什么：</strong>{summary.inference}</p>
    {summary.contexts.length > 0 && <details>
      <summary className="cursor-pointer text-accent-blue">联系经济和社会环境，接着看什么</summary>
      <div className="mt-2 space-y-2">{summary.contexts.map(context => <p key={context.name}><strong>{context.name}：</strong>{context.path}</p>)}
        {background.length > 0 ? <><p className="text-xs text-text-muted">近3天可能相关的背景报道，主题匹配不代表本次涨跌原因：</p>{background.map(item => <p key={item.url}><a href={item.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">{item.title}</a><span className="block text-xs text-text-muted">{item.source} · {item.date}</span></p>)}</> : <p className="text-xs text-text-muted">暂未取得直接相关的近期背景报道，以上是后续观察线索。</p>}
      </div>
    </details>}
    <p className="text-xs text-text-muted">{source === "sina" ? "新浪净流入 · 服务更新时间（非逐板块报价时间）" : "东方财富主力净流入 · 行情时间"}：{sectorTimeRange(items, source)}。板块可能重叠，不把资金相加当成全市场流入。</p>
  </aside>;
}
