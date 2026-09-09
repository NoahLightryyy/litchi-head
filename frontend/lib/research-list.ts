export interface ResearchEntry { code: string; name: string; note: string; updatedAt: string }
export function parseResearchList(raw: string | null): ResearchEntry[] {
  if (raw === null) return [];
  const value: unknown = JSON.parse(raw);
  if (!Array.isArray(value) || value.length > 500) throw new Error("自选数据格式无效");
  const codes = new Set<string>();
  return value.map((item: unknown) => {
    if (!item || typeof item !== "object") throw new Error("自选记录无效");
    const record = item as Record<string, unknown>;
    if (typeof record.code !== "string" || !/^\d{6}$/.test(record.code) || codes.has(record.code) ||
        typeof record.name !== "string" || !record.name.trim() || record.name.length > 100 ||
        typeof record.note !== "string" || record.note.length > 2000 ||
        typeof record.updatedAt !== "string" || !Number.isFinite(Date.parse(record.updatedAt))) throw new Error("自选记录无效");
    codes.add(record.code);
    return record as unknown as ResearchEntry;
  });
}
