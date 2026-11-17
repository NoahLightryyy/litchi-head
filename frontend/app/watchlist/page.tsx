"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { ResearchEntry } from "@/lib/research-list";
import { useResearchList } from "@/lib/hooks/use-research-list";
import { useDebounce } from "@/lib/hooks/use-debounce";
import { addWatchEntry, searchWatchStocks } from "@/lib/watchlist-reminders";
import { WatchReminders } from "@/components/stock/watch-reminders";

const button = "rounded border border-bg-tertiary px-3 py-2 text-sm text-accent-blue disabled:opacity-40";

function SavedStock({ entry, onNote, onRemove }: { entry: ResearchEntry; onNote: (note: string) => boolean; onRemove: () => void }) {
  const [note, setNote] = useState(entry.note);
  const [message, setMessage] = useState("");
  return <article className="space-y-4 rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <Link href={`/stock/${entry.code}`} className="text-lg font-semibold text-accent-blue">{entry.name} <span className="text-sm font-normal">{entry.code} →</span></Link>
      <button className="text-sm text-text-muted" onClick={onRemove}>移除自选</button>
    </div>
    <WatchReminders code={entry.code} />
    <details className="border-t border-bg-tertiary pt-3 text-sm">
      <summary className="cursor-pointer text-text-muted">{entry.note ? "我的备注（已保存）" : "随手记一句（选填）"}</summary>
      <form className="mt-3 space-y-2" onSubmit={event => { event.preventDefault(); if (onNote(note.trim())) setMessage("备注已保存"); }}>
        <label className="block">想记住什么？不用写专业分析
          <textarea value={note} onChange={event => { setNote(event.target.value); setMessage(""); }} maxLength={2000}
            placeholder="例如：先看看，不急着买；这是朋友提到的公司" className="mt-2 block w-full rounded border border-bg-tertiary bg-bg-primary p-2" />
        </label>
        <button className={button}>保存备注</button>
        {message && <p role="status">{message}</p>}
      </form>
    </details>
  </article>;
}

export default function WatchlistPage() {
  const { entries, error, readError, save } = useResearchList();
  const [input, setInput] = useState("");
  const query = useDebounce(input.trim(), 300);
  const [message, setMessage] = useState("");
  const [removed, setRemoved] = useState<ResearchEntry | null>(null);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [searchPage, setSearchPage] = useState(1);
  const search = useQuery({ queryKey: ["watchlist", "search", query], enabled: query.length >= 2,
    queryFn: ({ signal }) => searchWatchStocks(query, AbortSignal.any([signal, AbortSignal.timeout(20_000)])), retry: false, staleTime: 60_000 });
  const matches = search.data ?? [];
  const filtered = entries.filter(entry => entry.name.includes(filter.trim()) || entry.code.includes(filter.trim())).slice().reverse();
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const currentPage = Math.min(page, pages);
  const resultPage = Math.min(searchPage, Math.max(1, Math.ceil(matches.length / 10)));
  return <div className="mx-auto max-w-5xl space-y-5">
    <div><h1 className="text-2xl font-semibold">自选与跟踪</h1>
      <p className="mt-2 text-text-secondary">把关心的股票放这里，直接看价格变化、买入提醒和要小心的事。不用写分析，也不用先懂专业词。</p>
      <p className="mt-2 text-xs text-text-muted">打开页面时查看提醒；关掉页面不会后台盯盘或推送。已有分析直接读取，新的 AI 分析在详情页按需开启。</p>
    </div>
    {error && <p role="alert" className="text-accent-red">{error}</p>}
    <section aria-label="添加关注的股票" className="space-y-3 rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
      <h2 className="font-semibold">你想关注哪只股票？</h2>
      <label className="block text-sm">搜名称或代码就行
        <input value={input} onChange={event => { setInput(event.target.value); setSearchPage(1); }} placeholder="例如：中邮科技，或 688648" className="mt-2 block w-full rounded border border-bg-tertiary bg-bg-primary p-3" />
      </label>
      {input.trim().length === 1 && <p className="text-sm text-text-muted">再输入一个字，或者输入完整股票代码。</p>}
      {input.trim().length >= 2 && input.trim() !== query && <p role="status">正在搜索…</p>}
      {query.length >= 2 && input.trim() === query && <>
        {search.fetchStatus === "paused" ? <p role="status">网络断了，联网后可以继续搜索。</p> : search.isFetching ? <p role="status">正在找这只股票…</p> : null}
        {search.isError && <p role="alert">暂时没搜到数据，可以换完整代码试试。<button className="ml-2 text-accent-blue" onClick={() => void search.refetch()}>重新搜索</button></p>}
        {search.isSuccess && !matches.length && <p role="status">没有找到匹配的股票，试试完整名称或六位代码。</p>}
        <ul className="divide-y divide-bg-tertiary">{matches.slice((resultPage - 1) * 10, resultPage * 10).map(company => {
          const exists = entries.some(entry => entry.code === company.code);
          return <li key={company.code} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <span>{company.name} <span className="text-sm text-text-muted">{company.code}</span></span>
            <button className={button} disabled={exists || !!readError} onClick={() => {
              if (save(addWatchEntry(entries, company, new Date().toISOString()))) { setMessage(`已关注${company.name}，下面可以看提醒。`); setPage(1); setFilter(""); }
            }}>{exists ? "已关注" : "加入自选"}</button>
          </li>;
        })}</ul>
        {matches.length > 10 && <div className="flex items-center gap-3 text-sm"><button className={button} disabled={resultPage === 1} onClick={() => setSearchPage(resultPage - 1)}>上一组结果</button><span>{resultPage} / {Math.ceil(matches.length / 10)}</span><button className={button} disabled={resultPage * 10 >= matches.length} onClick={() => setSearchPage(resultPage + 1)}>下一组结果</button></div>}
      </>}
      {message && <p role="status" className="text-sm text-accent-blue">{message}</p>}
    </section>
    {removed && <p role="status">已移除 {removed.name} <button className="text-accent-blue" onClick={() => { if (save(entries.some(entry => entry.code === removed.code) ? entries : [...entries, removed])) setRemoved(null); }}>撤销移除</button></p>}
    {entries.length > 0 ? <>
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">我关注的股票 · {entries.length} 只</h2>
        <input aria-label="查找我的自选" value={filter} onChange={event => { setFilter(event.target.value); setPage(1); }} placeholder="在我的自选里找" className="rounded border border-bg-tertiary bg-bg-secondary p-2" />
      </div>
      {!filtered.length && <p>自选里没有匹配项，试试其他名字或清空筛选。</p>}
      {filtered.slice((currentPage - 1) * 10, currentPage * 10).map(entry => <SavedStock key={entry.code} entry={entry}
        onNote={note => save(entries.map(item => item.code === entry.code ? { ...item, note, updatedAt: new Date().toISOString() } : item))}
        onRemove={() => { if (save(entries.filter(item => item.code !== entry.code))) setRemoved(entry); }} />)}
      {pages > 1 && <nav aria-label="自选分页" className="flex items-center gap-3 text-sm"><button className={button} disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>上一页</button><span>第 {currentPage} / {pages} 页 · 每页 10 只</span><button className={button} disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>下一页</button></nav>}
    </> : !error && <div className="rounded-lg border border-dashed border-bg-tertiary p-6">
      <h2 className="font-semibold">先加一只你关心的股票</h2><p className="mt-2 text-sm text-text-muted">不用填买入理由。添加后会自动查看行情和已有分析；从股票详情也能一键加入。</p>
    </div>}
    <details className="text-xs text-text-muted"><summary className="cursor-pointer">自选记录保存在哪里？</summary><p className="mt-2">保存在当前浏览器，不跨设备同步。清理浏览器数据会删除自选和备注；可在<Link href="/settings" className="text-accent-blue underline">设置中备份</Link>。</p></details>
  </div>;
}
