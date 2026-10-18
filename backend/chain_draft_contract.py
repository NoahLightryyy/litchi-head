"""AI inferred maps are separate from reviewed evidence maps."""
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sector_name: str = Field(min_length=1, max_length=80)


class DraftNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_]{1,24}$")
    label: str = Field(min_length=1, max_length=60)
    role: str = Field(min_length=1, max_length=250)
    verify: str = Field(min_length=1, max_length=250)


class DraftEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    explanation: str = Field(min_length=1, max_length=200)


class DraftGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    map_kind: Literal["industry_chain", "concept_structure"]
    scope: str = Field(min_length=1, max_length=500)
    nodes: list[DraftNode] = Field(min_length=2, max_length=8)
    edges: list[DraftEdge] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def references(self) -> Self:
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("duplicate node")
        seen: set[tuple[str, str]] = set()
        for edge in self.edges:
            pair = (edge.source, edge.target)
            if not set(pair) <= ids or edge.source == edge.target or pair in seen:
                raise ValueError("invalid edge")
            seen.add(pair)
        return self


class DraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    sector_code: str
    sector_name: str
    graph: DraftGraph
    generated_at: datetime
    model: str
    cached: bool = False
    review_status: Literal["ai_inferred_unverified"] = "ai_inferred_unverified"
