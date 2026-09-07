from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.data.chain_evidence import ChainEvidenceMap, load_chain_evidence

CATALOG = (
    Path(__file__).parents[2]
    / "docs/03-modules/10-frontend/chain-evidence/ai-industry.candidate.json"
)


def valid_map():
    return load_chain_evidence(CATALOG, sector_code="BK1629", sector_name="AI应用")


def test_source_backed_map_preserves_provenance_and_does_not_invent_companies():
    graph = valid_map()
    assert len(graph.nodes) == 4
    assert all(node.kind == "industry_activity" for node in graph.nodes)
    assert not graph.edges
    assert graph.sources[0].published_on.isoformat() == "2024-07-02"


def test_sector_identity_must_match():
    with pytest.raises(ValueError, match="identity"):
        load_chain_evidence(CATALOG, sector_code="BK1650", sector_name="通信技术")


@pytest.mark.parametrize(
    "failure", ["duplicate", "missing_source", "no_source", "future", "unsafe_url"],
)
def test_invalid_provenance_fails_closed(failure):
    data = deepcopy(valid_map().model_dump(mode="json"))
    if failure == "duplicate":
        data["nodes"].append(data["nodes"][0])
    elif failure == "missing_source":
        data["nodes"][0]["source_ids"] = ["unknown"]
    elif failure == "no_source":
        data["nodes"][0]["source_ids"] = []
    elif failure == "future":
        data["sources"][0]["published_on"] = "2099-01-01"
    else:
        data["sources"][0]["url"] = "javascript:alert(1)"
    with pytest.raises(ValidationError):
        ChainEvidenceMap.model_validate(data)


@pytest.mark.parametrize("failure", ["supplier", "missing_node", "self", "missing_source"])
def test_invalid_relationships_are_rejected(failure):
    data = valid_map().model_dump(mode="json")
    edge = {"source_node": "base", "target_node": "framework", "relation": "industry_sequence",
            "source_ids": ["miit-ai-2024"], "description": "资料中的层次顺序"}
    if failure == "supplier":
        edge["relation"] = "supplies"
    elif failure == "missing_node":
        edge["target_node"] = "unknown"
    elif failure == "self":
        edge["target_node"] = "base"
    else:
        edge["source_ids"] = ["unknown"]
    data["edges"] = [edge]
    with pytest.raises(ValidationError):
        ChainEvidenceMap.model_validate(data)
