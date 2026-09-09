"use client";
import { useSyncExternalStore, useMemo, useState } from "react";
import { parseHoldings, type Holding } from "../portfolio";
const key = "litchi.holdings.v1";
const event = "litchi-holdings";
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(event, callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener(event, callback); };
}
function snapshot() { try { return localStorage.getItem(key); } catch { return "storage-unavailable"; } }
export function useHoldings() {
  const raw = useSyncExternalStore(subscribe, snapshot, () => null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const parsed = useMemo(() => { try { return { entries: parseHoldings(raw), error: null }; }
    catch { return { entries: [] as Holding[], error: "本机持仓数据无法读取，已停止写入，请先备份并检查浏览器存储。" }; } }, [raw]);
  function save(entries: Holding[]) {
    try {
      parseHoldings(snapshot());
      const encoded = JSON.stringify(entries);
      try { parseHoldings(encoded); } catch { setWriteError("请核对6位代码、有效日期和非负金额，记录尚未保存。"); return false; }
      localStorage.setItem(key, encoded);
      window.dispatchEvent(new Event(event));
      setWriteError(null);
      return true;
    } catch { setWriteError("保存失败，持仓数据未更新。请检查浏览器存储是否可用。"); return false; }
  }
  return { entries: parsed.entries, error: parsed.error ?? writeError, readError: parsed.error, save };
}
