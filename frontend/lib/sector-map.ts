export type MapCitation = { source_id: string; quote: string };
export type MapNode = { id: string; label: string; explanation: string; citations: MapCitation[] };
export type MapEdge = { source: string; target: string; explanation: string; citations: MapCitation[] };
export type MapVersion = {
  schema_version: 1; version: number; sector_code: string; generated_at: string;
  evidence_revision: string; model: string; review_status: "ai_unreviewed";
  evidence: {
    sector_code: string; sector_name: string; board_kind: "industry" | "concept";
    collected_at: string; members_as_of: string; member_count: number;
    sampled_codes: string[]; gaps: string[];
    sources: { id: string; title: string; url: string; published_on: string | null;
      stock_code: string; excerpt: string }[];
  };
  graph: { map_kind: "industry_chain" | "concept_relationship" | "market_structure";
    scope: string; nodes: MapNode[]; edges: MapEdge[] };
};
export type MapView = {
  current: MapVersion | null;
  history: { version: number; generated_at: string }[];
  automatic_updates: false;
};

export function mapTitle(kind: MapVersion["graph"]["map_kind"]) {
  return { industry_chain: "产业环节图", concept_relationship: "概念关联图",
    market_structure: "市场结构图" }[kind];
}

export function mapMatchesSector(view: MapView, sectorId: string): boolean {
  return !view.current || (view.current.sector_code === sectorId
    && view.current.evidence.sector_code === sectorId);
}
