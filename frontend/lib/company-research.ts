export interface CompanySource {
  id: string;
  title: string;
  url: string;
  published_at: string | null;
  excerpt: string;
}

export interface CitedInsight {
  text: string;
  basis: "disclosed" | "inference";
  source_ids: string[];
  stock_impact?: { mechanism: string; horizon: string; conditions: string } | null;
}

export interface CompanyResearch {
  schema_version: 1;
  stock_code: string;
  company_name: string;
  generated_at: string;
  fetched_at: string;
  model: string;
  review_status: "ai_unreviewed";
  purpose: "company_context_only";
  sources: CompanySource[];
  gaps: string[];
  interpretation: {
    niche: CitedInsight;
    upstream: CitedInsight;
    role: CitedInsight;
    downstream: CitedInsight;
    highlights: CitedInsight[];
    watchpoints: CitedInsight[];
    competition?: CitedInsight[];
  };
}

export function parseCompanyResearch(value: unknown, code: string): CompanyResearch | null {
  if (value === null) return null;
  const data = value as CompanyResearch;
  const validString = (value: unknown): value is string => typeof value === "string" && !!value.trim();
  const validTime = (value: unknown) => validString(value)
    && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
  const fail = (): never => { throw new Error("公司解读校验失败，请重试"); };
  if (!data || data.schema_version !== 1 || data.stock_code !== code
    || !validString(data.company_name) || !validString(data.model)
    || !validTime(data.generated_at) || !validTime(data.fetched_at)
    || data.review_status !== "ai_unreviewed" || data.purpose !== "company_context_only"
    || !Array.isArray(data.sources) || !data.sources.length
    || !Array.isArray(data.gaps) || !data.gaps.every(validString)) return fail();
  const ids = new Set<string>();
  for (const source of data.sources) {
    if (!source || !validString(source.id) || ids.has(source.id)
      || !validString(source.title) || !validString(source.excerpt)
      || typeof source.url !== "string"
      || (source.published_at !== null && (typeof source.published_at !== "string"
        || !/^\d{4}-\d{2}-\d{2}$/.test(source.published_at)
        || !Number.isFinite(Date.parse(source.published_at))))) return fail();
    try {
      const url = new URL(source.url);
      if (url.protocol !== "https:" || url.hostname !== "vip.stock.finance.sina.com.cn"
        || url.username || url.password) return fail();
    } catch { return fail(); }
    ids.add(source.id);
  }
  const result = data.interpretation;
  if (!result || !Array.isArray(result.highlights) || !Array.isArray(result.watchpoints)
    || result.highlights.length < 1 || result.highlights.length > 4
    || result.watchpoints.length < 1 || result.watchpoints.length > 4) return fail();
  if (result.competition !== undefined && (!Array.isArray(result.competition)
    || result.competition.length > 4)) return fail();
  for (const item of [result.niche, result.upstream, result.role, result.downstream,
    ...result.highlights, ...result.watchpoints, ...(result.competition ?? [])]) {
    if (item?.stock_impact != null) {
      for (const [key, max] of [["mechanism",240],["horizon",120],["conditions",240]] as const) {
        if (!validString(item.stock_impact[key]) || item.stock_impact[key].length > max) return fail();
      }
    }
    if (!item || !validString(item.text) || item.text.length > 400
      || !["disclosed", "inference"].includes(item.basis)
      || !Array.isArray(item.source_ids) || !item.source_ids.length || item.source_ids.length > 3
      || new Set(item.source_ids).size !== item.source_ids.length
      || !item.source_ids.every((id) => ids.has(id))) return fail();
  }
  return data;
}
