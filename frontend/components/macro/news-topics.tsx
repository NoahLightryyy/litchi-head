"use client";

import { useMemo, useState } from "react";
import type { HotNewsItem } from "@/lib/types/market";
import { prepareNews, prepareNewsReports, summarizeNews, type NewsWindow, type NewsTopic } from "@/lib/news-topics";

export function NewsTopics({items, sampledAt, refreshFailed = false}: {
  items: HotNewsItem[]; sampledAt: number; refreshFailed?: boolean;
}) {
  const [channel, setChannel] = useState<string | null>(null);
  const channels = useMemo(() => [...new Set(items.map(item => item.source))].sort(), [items]);
  const activeChannel = channel && channels.includes(channel) ? channel : null;
  const [window, setWindow] = useState<NewsWindow>("all");
  const [selected, setSelected] = useState<{kind: "topic" | "focus"; label: string} | null>(null);
  const channelItems = useMemo(() => activeChannel ? items.filter(item => item.source === activeChannel) : items, [items, activeChannel]);
  const cleaned = useMemo(() => prepareNews(channelItems, sampledAt), [channelItems, sampledAt]);
  const reports = useMemo(() => prepareNewsReports(channelItems, sampledAt), [channelItems, sampledAt]);
  const summary = useMemo(() => summarizeNews(cleaned.items, window, sampledAt), [cleaned, window, sampledAt]);
  const selection = selected ? (selected.kind === "topic" ? summary.topics : summary.focuses).find(x => x.label === selected.label) : null;
  const visible = reports.filter(item =>
    (window === "all" || (item.publishedAt !== null && sampledAt - item.publishedAt <= (window === "24h" ? 86400000 : 7 * 86400000)))
    && (!selected || selection?.ids.includes(item.id)));
  const maximum = Math.max(1, ...summary.topics.map(t => t.ids.length));
  const select = (kind: "topic" | "focus", topic: NewsTopic) => setSelected(value => value?.label === topic.label && value.kind === kind ? null : {kind, label: topic.label});
  const knownDates = summary.sample.flatMap(item => item.publishedAt === null ? [] : [item.publishedAt]);
  const formatDate = (timestamp: number) => new Date(timestamp).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false});

  return <div className="grid gap-4 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] p-4">
    <aside aria-label="新闻热点速览" className="min-w-0 rounded-lg border border-accent-blue/20 bg-accent-blue/5 p-4 md:order-2">
      <div className="flex items-center justify-between gap-2"><h3 className="font-semibold text-text-primary">热点速览</h3><span className="text-xs text-text-muted">标题提取</span></div>
      <div className="mt-3 flex flex-wrap gap-2" aria-label="新闻统计范围">
        {([['all', '当前快讯'], ['24h', '近 24 小时'], ['7d', '近 7 天']] as const).map(([value, label]) => <button key={value} aria-pressed={window === value}
          onClick={() => {setWindow(value); setSelected(null);}}
          className={`rounded px-2 py-1 text-xs focus-visible:outline-2 focus-visible:outline-accent-blue ${window === value ? 'bg-accent-blue text-white' : 'bg-bg-secondary text-text-secondary'}`}>{label}</button>)}
      </div>
      <label className="mt-3 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        新闻渠道
        <select aria-label="新闻渠道" value={activeChannel ?? ""}
          onChange={event => {setChannel(event.target.value || null); setSelected(null);}}
          className="max-w-full rounded border border-bg-tertiary bg-bg-secondary px-2 py-2 text-text-primary">
          <option value="">全部渠道（{channels.length}）</option>
          {channels.map(source => <option key={source} value={source}>{source}（{items.filter(item => item.source === source).length}条）</option>)}
        </select>
      </label>
      <p className="mt-2 text-xs text-text-muted">已取得：{channels.join("、")}。渠道可能转载同一报道。</p>
      <p className="mt-3 text-xs text-text-muted">{summary.sample.length} 条去重快讯 · 字越大，提及报道越多</p>
      {refreshFailed && <p role="status" className="mt-2 text-xs text-accent-gold">刷新失败，以下为上次取得的新闻样本。</p>}
      {summary.topics.length ? <>
        <div aria-label="热点词云" className="my-4 flex min-h-36 flex-wrap items-center justify-center gap-x-4 gap-y-2 rounded-lg bg-bg-secondary/80 p-3">
          {summary.topics.map((topic, index) => <button key={topic.label} aria-pressed={selected?.kind === 'topic' && selected.label === topic.label}
            aria-label={`${topic.label}，${topic.ids.length} 条报道`} title={`${topic.ids.length} 条报道，点击筛选`}
            onClick={() => select('topic', topic)} style={{fontSize: `${14 + 17 * topic.ids.length / maximum}px`}}
            className={`max-w-full break-words rounded px-1 py-1 leading-tight hover:bg-accent-blue/10 focus-visible:outline-2 focus-visible:outline-accent-blue ${index < 3 ? 'font-semibold text-accent-blue' : 'text-text-secondary'} ${selected?.label === topic.label ? 'ring-1 ring-accent-blue bg-accent-blue/10' : ''}`}>
            {topic.label}<span className="ml-1 align-super text-[10px] font-normal text-text-muted">{topic.ids.length}</span>
          </button>)}
        </div>
        <p className="text-sm leading-relaxed text-text-primary">本批报道较多提及<strong className="font-semibold">{summary.topics.slice(0, 3).map(t => t.label).join('、')}</strong>。</p>
      </> : <p role="status" className="py-8 text-center text-sm text-text-muted">{summary.sample.length ? '暂未提取到稳定主题，可直接阅读快讯。' : '此范围暂无有效新闻。'}</p>}
      {summary.focuses.length > 0 && <div className="mt-4 border-t border-accent-blue/15 pt-3">
        <p className="mb-2 text-xs font-medium text-text-secondary">报道关注点</p>
        <div className="flex flex-wrap gap-2">{summary.focuses.map(topic => <button key={topic.label} onClick={() => select('focus', topic)}
          aria-pressed={selected?.kind === 'focus' && selected.label === topic.label}
          className={`rounded border px-2 py-1 text-xs hover:bg-bg-secondary ${selected?.label === topic.label ? 'border-accent-blue text-accent-blue' : 'border-bg-tertiary text-text-secondary'}`}>
          {topic.label} · {topic.ids.length}</button>)}</div>
      </div>}
      <details className="mt-4 text-xs text-text-muted">
        <summary className="cursor-pointer text-accent-blue">统计口径与时间</summary>
        <p className="mt-2 leading-relaxed">每渠道最多采样 100 条（财联社单次 20 条），非全网热度，也不保证覆盖完整 24 小时或 7 天。渠道数量不代表独立核验次数。仅统计所选渠道当前返回的标题。报道列表保留各渠道原文；词云按同标题合并，一篇新闻对同一主题只计一次；同义词归并。关注点按标题关键词提取，可能遗漏或误分，不判断利好利空或预测涨跌。</p>
        <p className="mt-2">{summary.unknownDates} 条发布时间未确认，不进入近 24 小时/近 7 天统计。{cleaned.invalid} 条无效标题已排除，{cleaned.duplicates} 条重复标题已合并。</p>
        {knownDates.length > 0 && <p className="mt-2">已知发布时间：{formatDate(Math.min(...knownDates))} — {formatDate(Math.max(...knownDates))}（北京时间）</p>}
        <p className="mt-2">样本读取：{formatDate(sampledAt)}（北京时间，并非新闻发布时间）</p>
      </details>
    </aside>
    <div className="min-w-0 md:order-1">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-text-muted">
        <span role="status" aria-live="polite">{selected ? `${selected.label} · ` : ''}{visible.length} 条报道 · 保留各渠道出处</span>
        {selected && <button className="text-accent-blue hover:underline" onClick={() => setSelected(null)}>清除主题筛选</button>}
      </div>
      <div className="max-h-[480px] overflow-y-auto divide-y divide-bg-tertiary" aria-label="主题相关新闻">
        {visible.map(item => <article key={item.reportKey} className="py-3 first:pt-0">
          {item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-sm leading-relaxed text-text-primary hover:text-accent-blue">{item.title}<span className="ml-1 text-xs text-text-muted" aria-label="新标签页打开原文">↗</span></a> : <p className="text-sm leading-relaxed text-text-primary">{item.title}</p>}
          <p className="mt-2 text-[11px] text-text-muted">{item.source} · {item.publishedAt === null ? '发布时间未确认' : `${formatDate(item.publishedAt)} 北京时间`}</p>
        </article>)}
        {visible.length === 0 && <p className="p-6 text-center text-sm text-text-muted">暂无匹配快讯，可切换时间范围{selected ? '或清除筛选' : ''}。</p>}
      </div>
    </div>
  </div>;
}
