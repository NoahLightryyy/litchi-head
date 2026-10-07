import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { parseChainInterpretation } from "../lib/chain-interpretation.ts";

const graph = JSON.parse(readFileSync(new URL("../../src/data/catalogs/chain/BK1106.json", import.meta.url), "utf8"));
const valid = () => ({ sector_code: graph.sector_code, evidence_revision: "a".repeat(64),
  generated_at: "2026-10-06T09:00:00Z", model: "test", cached: false,
  review_status: "ai_unreviewed", citation_coverage: 1,
  interpretation: { summary: "研发流程示意", stages: graph.nodes.map((node: {id: string; label: string; source_ids: string[]}) => ({node_id: node.id, explanation: node.label, source_ids: node.source_ids})) },
});

test("AI interpretations retain review status and exact sourced nodes", () => {
  assert.equal(parseChainInterpretation(valid(), graph).interpretation.stages.length, 5);
});

test("AH market interpretation preserves issuer and both listings", () => {
  const market = JSON.parse(readFileSync(new URL("../../src/data/catalogs/chain/BK0499.json", import.meta.url), "utf8"));
  const value = valid();
  value.sector_code = market.sector_code;
  value.interpretation.stages = market.nodes.map((node: {id: string; label: string; source_ids: string[]}) => ({node_id: node.id, explanation: node.label, source_ids: node.source_ids}));
  assert.equal(parseChainInterpretation(value, market).interpretation.stages.length, 3);
  assert.equal(market.map_kind, "market_structure");
  value.interpretation.stages[0].source_ids = ["samr-drug-registration-2020"];
  assert.throws(() => parseChainInterpretation(value, market));
});

test("foreign sector, fabricated citation, missing and duplicate stages fail closed", () => {
  for (const fault of ["sector", "citation", "missing", "duplicate", "review"]){
    const value = valid();
    if (fault === "sector") value.sector_code = "BK1216";
    if (fault === "citation") value.interpretation.stages[0].source_ids = ["invented"];
    if (fault === "missing") value.interpretation.stages.pop();
    if (fault === "duplicate") value.interpretation.stages[1] = value.interpretation.stages[0];
    if (fault === "review") value.review_status = "verified";
    assert.throws(() => parseChainInterpretation(value, graph));
  }
});
