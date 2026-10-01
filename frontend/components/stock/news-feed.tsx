"use client";

import {useState, useSyncExternalStore} from "react";
import {useQuery} from "@tanstack/react-query";
import {fetchNewsDisplay, NewsDisplayError} from "@/lib/api/news-display";
import {newsPage, publicationLabel, type NewsKind} from "@/lib/news-display";

const LABELS: Record<NewsKind, string> = {report: "相关新闻", announcement: "公司公告", mention: "提及该股"};
const SOURCES = {eastmoney: "东方财富搜索", cninfo: "巨潮资讯"};
const STATES = {success: "检索完成", empty: "当前范围无匹配", partial: "部分结果", failed: "获取失败"};
const LIMITS: Record<string, string> = {SOURCE_TIMEOUT: "请求超时", SOURCE_UNAVAILABLE: "来源暂不可用",
  SEARCH_WINDOW_LIMITED: "仅获取部分搜索页", INVALID_ROWS_SKIPPED: "已过滤无效记录", PUBLICATION_TIME_MISSING: "部分记录缺少发布时间"};
function subscribeOnline(notify: () => void) {
  window.addEventListener("online", notify); window.addEventListener("offline", notify);
  return () => { window.removeEventListener("online", notify); window.removeEventListener("offline", notify); };
}

/** Display-only retrieval; never changes the investment evidence gate. */
export function NewsFeed({code}: {code: string}) {
  const [days, setDays] = useState(30);
  const [kind, setKind] = useState<NewsKind | "all">("all");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const online = useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
  const query = useQuery({queryKey: ["stocks", code, "news-display", days],
    queryFn: ({signal}) => fetchNewsDisplay(code, days, AbortSignal.any([signal, AbortSignal.timeout(15000)])),
    retry: false, staleTime: 120000, refetchOnWindowFocus: false});
  const data = query.data;
  const sources = query.error instanceof NewsDisplayError ? query.error.result?.sources : data?.sources;
  const view = newsPage(data?.items ?? [], kind, keyword, page);
  const button = "rounded border border-bg-tertiary px-3 py-1.5 text-xs disabled:opacity-40 enabled:hover:opacity-80";
  return <section aria-label="相关新闻与公告" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="font-semibold text-text-primary">相关新闻与公告</h2>
        <p className="mt-1 text-xs text-text-muted">自动检索公司相关新闻与官方公告 · 发布时间按北京时间</p></div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-text-muted">时间范围 <select aria-label="新闻时间范围" value={days} onChange={e => {setDays(Number(e.target.value)); setPage(1);}} className="bg-bg-primary rounded p-2">
          {[7,30,90].map(d => <option key={d} value={d}>近 {d} 天</option>)}
        </select></label>
        <button className={button} disabled={query.isFetching || !online} onClick={() => void query.refetch()}>{query.isFetching ? "检索中…" : "刷新新闻"}</button>
      </div>
    </div>
    {!online && <p role="status" className="text-sm text-accent-gold">当前离线；已加载内容仍可阅读，联网后可刷新。</p>}
    {query.isError && <p role="alert" className="rounded bg-accent-red/10 p-3 text-sm text-accent-red">{query.error instanceof NewsDisplayError ? query.error.message : "新闻检索连接失败，请检查网络后重试"}{data ? "；下方保留上次结果，尚未更新。" : ""}</p>}
    {query.isPending && online && <p role="status" className="py-8 text-center text-sm text-text-muted">正在搜索新闻与公司公告…</p>}
    {data && <>
      <div className="flex flex-wrap gap-2 text-xs text-text-muted">
        <span>{data.company_name ?? code} · {data.start_date} — {data.end_date}</span>
        <span>取得 {data.items.length} 条{data.cached ? " · 缓存结果" : ""}</span>
        <span>检索于 {new Date(data.fetched_at).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai", hour12: false})}</span>
      </div>
      {data.status === "partial" && <p role="status" className="rounded bg-accent-gold/10 p-3 text-sm text-accent-gold">部分来源或记录不完整，先显示可用内容；可展开下方检索来源查看原因。</p>}
      {data.items.some(n => n.published_at === null) && <p className="text-xs text-text-muted">缺少发布时间的条目单独标注，不能确认其属于所选时间范围。</p>}
      <div className="flex flex-wrap items-center gap-2" aria-label="新闻分类">
        {(["all", "report", "announcement", "mention"] as const).map(k => <button key={k} aria-pressed={kind === k} onClick={() => {setKind(k); setPage(1);}} className={`${button} ${kind === k ? "bg-accent-blue text-white" : "text-text-secondary"}`}>{k === "all" ? "全部" : LABELS[k]} {data.items.filter(n => k === "all" || n.kind === k).length}</button>)}
        <input aria-label="搜索当前新闻" placeholder="搜索已取得的内容" value={keyword} onChange={e => {setKeyword(e.target.value);setPage(1);}} className="min-w-0 rounded border border-bg-tertiary bg-bg-primary px-3 py-2 text-sm" />
      </div>
      {kind === "mention" && <p className="text-xs text-text-muted">这些报道的搜索摘要提及该股，主题可能涉及多家公司；未据此认定为公司公告或已核验事实。</p>}
      {!view.items.length ? <p role="status" className="py-6 text-sm text-text-muted">{data.status === "empty" ? "所选时间范围内，当前检索来源未找到匹配新闻或公告。" : "当前分类或关键词没有匹配条目。"}</p> : <ul className="divide-y divide-bg-tertiary">
        {view.items.map(item => <li key={item.id} className="py-4 space-y-2">
          <div className="flex flex-wrap items-baseline gap-2"><span className="rounded bg-bg-tertiary px-2 py-0.5 text-xs text-text-muted">{LABELS[item.kind]}</span><h3 className="text-sm font-medium text-text-primary">{item.title}</h3></div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted"><span>{publicationLabel(item)}</span>
            {item.provenance.map(p => <a key={`${p.source}:${p.publisher}:${p.url}`} href={p.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue hover:underline">{p.publisher} · 查看原文 ↗</a>)}
          </div>
        </li>)}
      </ul>}
      {view.total > 10 && <nav aria-label="新闻分页" className="flex flex-wrap justify-center items-center gap-2">
        <button className={button} disabled={view.current === 1} onClick={() => setPage(1)}>首页</button>
        <button className={button} disabled={view.current === 1} onClick={() => setPage(view.current - 1)}>上一页</button>
        <span className="text-xs text-text-muted">第 {view.current} / {view.pages} 页 · {view.total} 条</span>
        <button className={button} disabled={view.current === view.pages} onClick={() => setPage(view.current + 1)}>下一页</button>
        <button className={button} disabled={view.current === view.pages} onClick={() => setPage(view.pages)}>尾页</button>
      </nav>}
    </>}
    {sources && <details className="border-t border-bg-tertiary pt-3 text-xs text-text-muted"><summary className="cursor-pointer">检索来源与范围</summary>
      <ul className="mt-2 space-y-2">{sources.map(s => <li key={s.source}>{SOURCES[s.source]}：{STATES[s.status]} · 检索 {s.scanned} 条候选，匹配 {s.matched} 条{s.error_code ? ` · ${LIMITS[s.error_code] ?? "来源存在限制"}` : ""}</li>)}</ul>
      <p className="mt-2">结果可能包含转载和搜索摘要，未读取全部原文。检索完成不等于覆盖全部市场消息；此处内容不会自动成为 AI 决策证据。</p>
    </details>}
  </section>;
}
