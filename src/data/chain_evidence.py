"""Source-independent, evidence-backed industry map contract.

Industry stages and company supply relationships are separate claims. Loading a
catalog never promotes industry examples into verified supplier/customer edges.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ChainSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    url: HttpUrl
    published_on: date
    checked_on: date
    locator: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.published_on > self.checked_on:
            raise ValueError("source cannot be reviewed before publication")
        return self


class ChainEvidenceNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: Literal["industry_activity", "company", "market_entity"]
    stage: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    stock_code: str | None = Field(default=None, pattern=r"^\d{6}$")

    @model_validator(mode="after")
    def company_identity(self) -> Self:
        if self.stock_code is not None and self.kind != "company":
            raise ValueError("an industry activity cannot identify a listed company")
        return self


class ChainEvidenceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_node: str
    target_node: str
    relation: Literal["industry_sequence", "supplies", "listing_relationship"]
    source_ids: tuple[str, ...] = Field(min_length=1)
    description: str = Field(min_length=1)


class ChainEvidenceMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    map_kind: Literal["industry_chain", "market_structure"] = "industry_chain"
    sector_code: str = Field(pattern=r"^BK\d{4}$")
    sector_name: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    sources: tuple[ChainSource, ...] = Field(min_length=1)
    nodes: tuple[ChainEvidenceNode, ...] = Field(min_length=1)
    edges: tuple[ChainEvidenceEdge, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        sources = {item.id for item in self.sources}
        nodes = {item.id: item for item in self.nodes}
        if len(sources) != len(self.sources) or len(nodes) != len(self.nodes):
            raise ValueError("duplicate source or node id")
        for node in self.nodes:
            if (node.kind == "market_entity") != (self.map_kind == "market_structure"):
                raise ValueError("market entities must belong to a market structure")
            if not set(node.source_ids) <= sources:
                raise ValueError("node references unknown evidence")
        edge_keys: set[tuple[str, str, str]] = set()
        for edge in self.edges:
            if edge.source_node not in nodes or edge.target_node not in nodes:
                raise ValueError("edge references unknown node")
            if edge.source_node == edge.target_node:
                raise ValueError("self edges are not supported")
            if not set(edge.source_ids) <= sources:
                raise ValueError("edge references unknown evidence")
            key = (edge.source_node, edge.target_node, edge.relation)
            if key in edge_keys:
                raise ValueError("duplicate edge")
            edge_keys.add(key)
            expected = {
                "supplies": "company", "industry_sequence": "industry_activity",
                "listing_relationship": "market_entity",
            }[edge.relation]
            if any(nodes[item].kind != expected for item in (edge.source_node, edge.target_node)):
                raise ValueError("industry stages cannot be promoted to company supply edges")
        return self


def load_chain_evidence(path: Path, *, sector_code: str, sector_name: str) -> ChainEvidenceMap:
    """Read an explicitly selected local catalog; no network fetch or name guessing."""
    result = ChainEvidenceMap.model_validate_json(path.read_text(encoding="utf-8"))
    if (result.sector_code, result.sector_name) != (sector_code, sector_name):
        raise ValueError("catalog does not match the requested sector identity")
    return result


CATALOG_ROOT = Path(__file__).parent / "catalogs" / "chain"


def get_sector_chain(sector_code: str, sector_name: str) -> ChainEvidenceMap | None:
    """Only explicit, reviewed catalogs can populate a sector; absent is not inferred."""
    import re

    if re.fullmatch(r"BK\d{4}", sector_code) is None:
        return None
    path = CATALOG_ROOT / f"{sector_code}.json"
    if not path.is_file():
        return None
    return load_chain_evidence(path, sector_code=sector_code, sector_name=sector_name)
