const KEY = "litchi-search-history-v1";
const EVENT = "litchi-search-history-change";
let memory = "[]";
let memoryOnly = false;

export function parseSearchHistory(raw: string): string[] {
  try {
    const data: unknown = JSON.parse(raw);
    if (!Array.isArray(data)) return [];
    const seen = new Set<string>();
    return data.filter((value): value is string => typeof value === "string")
      .map(value => value.trim().slice(0, 80)).filter(value => {
        const id = value.toLocaleLowerCase();
        if (!value || seen.has(id)) return false;
        seen.add(id); return true;
      }).slice(0, 20);
  } catch { return []; }
}

export function addSearchHistory(history: string[], keyword: string): string[] {
  return parseSearchHistory(JSON.stringify([keyword, ...history]));
}
export function searchHistorySnapshot(): string {
  if (memoryOnly) return memory;
  try { return localStorage.getItem(KEY) ?? "[]"; } catch { return memory; }
}
export function saveSearchHistory(items: string[]): void {
  memory = JSON.stringify(parseSearchHistory(JSON.stringify(items)));
  try { localStorage.setItem(KEY, memory); } catch { memoryOnly = true; }
  window.dispatchEvent(new Event(EVENT));
}
export function subscribeSearchHistory(listener: () => void): () => void {
  const storage = (event: StorageEvent) => { if (event.key === KEY || event.key === null) listener(); };
  window.addEventListener(EVENT, listener);
  window.addEventListener("storage", storage);
  return () => { window.removeEventListener(EVENT, listener); window.removeEventListener("storage", storage); };
}
