"use client";
import { useState } from "react";
import Link from "next/link";
import type { ResearchEntry } from "@/lib/research-list";
import { useResearchList } from "@/lib/hooks/use-research-list";
export default function WatchlistPage() {
  const { entries, error, readError, save } = useResearchList();
  const [code, setCode] = useState(""); const [name, setName] = useState("");
  const [note, setNote] = useState(""); const [message, setMessage] = useState("");
  const [removed, setRemoved] = useState<ResearchEntry | null>(null);
  const [query, setQuery] = useState("");
  return <div className="mx-auto max-w-5xl space-y-5">
    <h1 className="text-2xl font-semibold">自选与跟踪</h1>
    <p className="text-sm text-text-muted">保存在当前浏览器。记录关注公司和待验证假设；清理浏览器数据会删除记录，不跨设备同步。</p>
    {error && <p role="alert" className="text-accent-red">{error}</p>}
    <form className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 space-y-3" onSubmit={(e) => {
      e.preventDefault();
      const next = { code: code.trim(), name: name.trim(), note: note.trim(), updatedAt: new Date().toISOString() };
      const existed = entries.some((entry) => entry.code === next.code);
      if (save([...entries.filter((entry) => entry.code !== next.code), next])) {
        setMessage(existed ? "已更新关注记录" : "已加入自选"); setCode(""); setName(""); setNote("");
      }
    }}>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm">股票代码<input required pattern="[0-9]{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} className="block rounded border border-bg-tertiary bg-bg-primary p-2" /></label>
        <label className="text-sm">公司名称<input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className="block rounded border border-bg-tertiary bg-bg-primary p-2" /></label>
      </div>
      <label className="block text-sm">跟踪假设与验证条件<textarea maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 block w-full rounded border border-bg-tertiary bg-bg-primary p-2" placeholder="例如：下次财报中核对订单兑现与现金流变化" /></label>
      <button disabled={!!readError} className="rounded bg-accent-blue px-4 py-2 text-white disabled:opacity-40">保存自选</button>
      <p role="status" className="text-sm">{message}</p>
    </form>
    <input aria-label="搜索自选" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索自选名称或代码" className="w-full rounded border border-bg-tertiary bg-bg-secondary p-3" />
    {removed && <p role="status">已移除 {removed.name} <button className="text-accent-blue" onClick={() => { if (save([...entries.filter((item) => item.code !== removed.code), removed])) setRemoved(null); }}>撤销移除</button></p>}
    {!entries.length && !error && <p className="text-text-muted">暂无自选，添加关注公司后可记录假设并进入个股研究。</p>}
    {entries.filter((entry) => entry.name.includes(query.trim()) || entry.code.includes(query.trim())).map((entry) => <article key={entry.code} className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 space-y-2">
      <div className="flex flex-wrap justify-between gap-2"><Link className="text-accent-blue font-semibold" href={`/stock/${entry.code}`}>{entry.name} · {entry.code}</Link>
        <button onClick={() => { setCode(entry.code); setName(entry.name); setNote(entry.note); setMessage("修改后点击保存自选"); }} className="text-sm text-accent-blue">编辑记录</button></div>
      <p className="whitespace-pre-wrap text-sm">{entry.note || "尚未填写跟踪假设"}</p>
      <p className="text-xs text-text-muted">记录更新：{new Date(entry.updatedAt).toLocaleString("zh-CN")}</p>
      <Link className="text-sm text-accent-blue" href={`/screening?code=${entry.code}`}>加入研究对比</Link>
      <button className="ml-4 text-sm text-text-muted" onClick={() => { if (save(entries.filter((item) => item.code !== entry.code))) setRemoved(entry); }}>移除自选</button>
    </article>)}
  </div>;
}
