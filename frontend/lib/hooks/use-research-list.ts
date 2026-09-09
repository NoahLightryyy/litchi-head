"use client";
import { useSyncExternalStore, useMemo, useState } from "react";
import { parseResearchList, type ResearchEntry } from "../research-list";
const key = "litchi.research-list.v1";
const event = "litchi-research-list";
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(event, callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener(event, callback); };
}
function snapshot() { try { return localStorage.getItem(key); } catch { return "storage-unavailable"; } }
export function useResearchList() {
  const raw = useSyncExternalStore(subscribe, snapshot, () => null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const parsed = useMemo(() => { try { return { entries: parseResearchList(raw), error: null }; }
    catch { return { entries: [] as ResearchEntry[], error: "本机自选数据无法读取，已停止写入，请先备份并检查浏览器存储。" }; } }, [raw]);
  function save(entries: ResearchEntry[]) {
    try {
      parseResearchList(snapshot());
      const encoded = JSON.stringify(entries);
      parseResearchList(encoded);
      localStorage.setItem(key, encoded);
      window.dispatchEvent(new Event(event));
      setWriteError(null);
      return true;
    } catch { setWriteError("保存失败，自选数据未更新。请检查浏览器存储是否可用。"); return false; }
  }
  return { entries: parsed.entries, error: parsed.error ?? writeError, readError: parsed.error, save };
}
