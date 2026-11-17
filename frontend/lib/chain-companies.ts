import type { ChainDraft } from "./chain-draft";

export interface ChainCompany {
  node_id: string;
  name: string;
  business: string;
  influence: string;
  a_share_code: string | null;
  reference_status: "public_reference" | "ai_candidate";
  sources: { title: string; url: string; excerpt: string; accessed_at: string }[];
}
export interface ChainCompanies {
  schema_version: 1;
  sector_code: string;
  sector_name: string;
  graph_revision: string;
  graph_nodes: { id: string; label: string }[];
  companies: ChainCompany[];
  generated_at: string;
  model: string;
  cached: boolean;
  review_status: "ai_unreviewed";
}
const object = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("企业清单格式无效");
  return value as Record<string, unknown>;
};
const text = (value: unknown, max: number) => typeof value === "string" && value.trim().length > 0 && value.length <= max;
const stamp = (value: unknown) => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const safeUrl = (value: unknown) => {
  if (typeof value !== "string") return false;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password; }
  catch { return false; }
};
export function parseChainCompanies(value: unknown, draft: ChainDraft): ChainCompanies {
  const r = object(value);
  const nodes = draft.graph.nodes.map(({ id, label }) => ({ id, label }));
  if (r.schema_version !== 1 || r.sector_code !== draft.sector_code || r.sector_name !== draft.sector_name
    || r.review_status !== "ai_unreviewed" || !text(r.model, 100) || !stamp(r.generated_at)
    || typeof r.cached !== "boolean" || typeof r.graph_revision !== "string" || !/^[a-f0-9]{64}$/.test(r.graph_revision)
    || !Array.isArray(r.graph_nodes) || r.graph_nodes.length !== nodes.length
    || r.graph_nodes.some((raw, index) => { const node = object(raw); return node.id !== nodes[index].id || node.label !== nodes[index].label; })
    || !Array.isArray(r.companies) || r.companies.length < 1 || r.companies.length > 12) throw new Error("企业清单与当前产业结构不匹配");
  const names = new Set<string>(), codes = new Set<string>();
  for (const raw of r.companies) {
    const c = object(raw);
    if (!nodes.some((node) => node.id === c.node_id) || !text(c.name, 80) || !text(c.business, 250) || !text(c.influence, 250)
      || !["public_reference", "ai_candidate"].includes(String(c.reference_status))
      || !Array.isArray(c.sources) || c.sources.length > 3
      || (c.reference_status === "public_reference") !== (c.sources.length > 0)
      || !(c.a_share_code === null || (typeof c.a_share_code === "string" && /^\d{6}$/.test(c.a_share_code) && c.sources.length > 0))) throw new Error("企业资料校验失败");
    const name = (c.name as string).trim().toLowerCase();
    if (names.has(name) || (typeof c.a_share_code === "string" && codes.has(c.a_share_code))) throw new Error("企业清单包含重复公司");
    names.add(name);
    if (typeof c.a_share_code === "string") codes.add(c.a_share_code);
    for (const rawSource of c.sources) {
      const source = object(rawSource);
      if (!text(source.title, 120) || !safeUrl(source.url) || !text(source.excerpt, 2000) || !stamp(source.accessed_at)) throw new Error("企业来源无效");
    }
  }
  return r as unknown as ChainCompanies;
}
export const chainCompaniesKey = (draft: ChainDraft) => ["chain-companies", draft.sector_code, draft.sector_name, JSON.stringify(draft.graph)] as const;
