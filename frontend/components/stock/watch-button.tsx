"use client";
import { useState } from "react";
import Link from "next/link";
import { useResearchList } from "@/lib/hooks/use-research-list";
import { addWatchEntry } from "@/lib/watchlist-reminders";

export function WatchButton({ code, name }: { code: string; name: string }) {
  const { entries, save, error, readError } = useResearchList();
  const [added, setAdded] = useState(false);
  const exists = entries.some(item => item.code === code);
  return <div className="flex flex-wrap items-center gap-3 text-sm">
    {exists ? <Link className="text-accent-blue" href="/watchlist">★ 已加入自选 · 查看提醒</Link> :
      <button disabled={!!readError || !/^\d{6}$/.test(code) || !name.trim() || name === code} className="text-accent-blue disabled:opacity-50"
        onClick={() => { if (save(addWatchEntry(entries, { code, name }, new Date().toISOString()))) setAdded(true); }}>☆ 加入自选，方便看提醒</button>}
    {added && <span role="status" className="text-text-muted">已保存，不用填写理由。</span>}
    {error && <span role="alert" className="text-accent-red">{error}</span>}
  </div>;
}
