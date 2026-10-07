import type { ChainEvidence } from "./types/market.ts";

export interface ChainInterpretation {
  sector_code: string;
  evidence_revision: string;
  generated_at: string;
  model: string;
  cached: boolean;
  review_status: "ai_unreviewed";
  citation_coverage: number;
  interpretation: {
    summary: string;
    stages: { node_id: string; explanation: string; source_ids: string[] }[];
  };
}

export function parseChainInterpretation(value: unknown, evidence: ChainEvidence): ChainInterpretation {
  const data = value as ChainInterpretation;
  if (!data || data.sector_code !== evidence.sector_code
    || typeof data.evidence_revision !== "string" || !/^[a-f0-9]{64}$/.test(data.evidence_revision)
    || typeof data.generated_at !== "string" || !Number.isFinite(Date.parse(data.generated_at))
    || typeof data.model !== "string" || !data.model
    || typeof data.cached !== "boolean" || data.review_status !== "ai_unreviewed"
    || data.citation_coverage !== 1
    || typeof data.interpretation?.summary !== "string" || !data.interpretation.summary.trim()
    || !Array.isArray(data.interpretation.stages)) {
    throw new Error("AI 解读响应校验失败，原资料图仍可查看");
  }
  const stages = data.interpretation.stages;
  if (stages.length !== evidence.nodes.length || new Set(stages.map((s) => s?.node_id)).size !== stages.length) {
    throw new Error("AI 解读环节不完整，原资料图仍可查看");
  }
  for (const stage of stages) {
    const node = evidence.nodes.find((node) => node.id === stage?.node_id);
    if (!node || typeof stage.explanation !== "string" || !stage.explanation.trim()
      || !Array.isArray(stage.source_ids) || !stage.source_ids.length
      || new Set(stage.source_ids).size !== stage.source_ids.length
      || stage.source_ids.some((id) => !node.source_ids.includes(id))) {
      throw new Error("AI 解读引用校验失败，原资料图仍可查看");
    }
  }
  return data;
}
