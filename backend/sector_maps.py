"""Evidence-bound candidate maps, separate from the reviewed static catalog."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from backend.company_research import fetch_evidence
from src.data.providers.eastmoney_boards import board_snapshots

logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MapSource(StrictModel):
    id: str
    title: str
    url: HttpUrl
    published_on: str | None = None
    stock_code: str = Field(pattern=r"^\d{6}$")
    excerpt: str = Field(min_length=1, max_length=36000)


class MapEvidence(StrictModel):
    sector_code: str = Field(pattern=r"^BK\d{4}$")
    sector_name: str
    board_kind: Literal["industry", "concept"]
    collected_at: datetime
    members_as_of: datetime
    member_count: int
    sampled_codes: list[str]
    sources: list[MapSource] = Field(min_length=1)
    gaps: list[str]

    def revision(self) -> str:
        # Retrieval time changes are not new evidence. Publication dates and contents are.
        body = self.model_dump(mode="json", exclude={"collected_at", "members_as_of"})
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


class Citation(StrictModel):
    source_id: str
    quote: str = Field(min_length=8, max_length=500)


class MapNode(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    label: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=500)
    citations: list[Citation] = Field(min_length=1, max_length=5)


class MapEdge(StrictModel):
    source: str
    target: str
    explanation: str = Field(min_length=1, max_length=300)
    citations: list[Citation] = Field(min_length=1, max_length=5)


class MapGraph(StrictModel):
    map_kind: Literal["industry_chain", "concept_relationship", "market_structure"]
    scope: str = Field(min_length=1, max_length=800)
    nodes: list[MapNode] = Field(min_length=1, max_length=16)
    edges: list[MapEdge] = Field(max_length=30)

    @model_validator(mode="after")
    def validate_graph(self) -> MapGraph:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate nodes")
        pairs = [(edge.source, edge.target) for edge in self.edges]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Duplicate edges")
        for edge in self.edges:
            if edge.source not in ids or edge.target not in ids or edge.source == edge.target:
                raise ValueError("Invalid edge endpoint")
        return self


def validate_evidence(graph: MapGraph, evidence: MapEvidence) -> None:
    sources = {source.id: source for source in evidence.sources}
    if len(sources) != len(evidence.sources):
        raise ValueError("Duplicate source IDs")
    if evidence.board_kind == "industry" and graph.map_kind != "industry_chain":
        raise ValueError("Industry map kind mismatch")
    for item in [*graph.nodes, *graph.edges]:
        for citation in item.citations:
            source = sources.get(citation.source_id)
            if source is None or citation.quote not in source.excerpt:
                raise ValueError("Citation must quote an actual supplied excerpt")


class MapVersion(StrictModel):
    schema_version: Literal[1] = 1
    version: int = Field(ge=1)
    sector_code: str
    generated_at: datetime
    evidence_revision: str
    model: str
    review_status: Literal["ai_unreviewed"] = "ai_unreviewed"
    evidence: MapEvidence
    graph: MapGraph

    @model_validator(mode="after")
    def validate_version(self) -> MapVersion:
        if self.sector_code != self.evidence.sector_code:
            raise ValueError("Sector identity mismatch")
        if self.evidence_revision != self.evidence.revision():
            raise ValueError("Evidence digest mismatch")
        validate_evidence(self.graph, self.evidence)
        return self


class MapHistoryItem(StrictModel):
    version: int
    generated_at: datetime


class MapView(StrictModel):
    current: MapVersion | None
    history: list[MapHistoryItem]
    automatic_updates: Literal[False] = False


class MapStore:
    def __init__(self, path: Path = Path("data/sector_maps/versions.sqlite3")) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("CREATE TABLE IF NOT EXISTS versions (code TEXT, version INTEGER, "
                   "body TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(code, version))")
        return db

    def read(self, code: str, version: int | None = None) -> MapView:
        db = self.connect()
        try:
            rows = db.execute("SELECT body,digest FROM versions WHERE code=? "
                              "ORDER BY version DESC", (code,)).fetchall()
        finally:
            db.close()
        versions: list[MapVersion] = []
        for body, digest in rows:
            if hashlib.sha256(body.encode()).hexdigest() != digest:
                raise ValueError("Map storage checksum mismatch")
            item = MapVersion.model_validate_json(body)
            if item.sector_code != code:
                raise ValueError("Map storage identity mismatch")
            versions.append(item)
        selected = next((item for item in versions if version in (None, item.version)), None)
        return MapView(current=selected, history=[
            MapHistoryItem(version=item.version, generated_at=item.generated_at)
            for item in versions
        ])

    def save(self, graph: MapGraph, evidence: MapEvidence, model: str) -> MapVersion:
        validate_evidence(graph, evidence)
        db = self.connect()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                latest = db.execute("SELECT COALESCE(MAX(version),0) FROM versions WHERE code=?",
                                    (evidence.sector_code,)).fetchone()[0]
                result = MapVersion(version=latest + 1, sector_code=evidence.sector_code,
                                    generated_at=datetime.now(UTC),
                                    evidence=evidence.model_copy(deep=True),
                                    graph=graph.model_copy(deep=True),
                                    evidence_revision=evidence.revision(), model=model)
                body = result.model_dump_json()
                db.execute("INSERT INTO versions VALUES (?,?,?,?)", (
                    result.sector_code, result.version, body,
                    hashlib.sha256(body.encode()).hexdigest(),
                ))
            return result
        finally:
            db.close()


async def collect_map_evidence(code: str) -> MapEvidence:
    """Reuse existing board and filing providers, disclosing deterministic sampling."""
    detail = await asyncio.to_thread(board_snapshots.fetch_detail, code)
    if detail is None:
        raise LookupError("Board not found in official directory")
    members = await asyncio.to_thread(board_snapshots.fetch_members, code, detail.kind)
    if members.board_code != code or members.kind != detail.kind:
        raise ValueError("Board membership identity mismatch")
    selected = sorted({member.code for member in members.members})[:6]
    sources: list[MapSource] = []
    gaps = ["按股票代码顺序取前6家成分公司资料，不代表全板块或龙头排序；"
            "每份资料最多读取前4000字的节选，未覆盖全部公司及最新事件。",
            "节点和连线均为AI推断，尚未人工复核；"
            "原文引用匹配不代表推断已被证实，不用于确认企业供货关系。"]

    async def collect(stock: str) -> None:
        try:
            evidence = await fetch_evidence(stock)
            if evidence.stock_code != stock:
                raise ValueError("Company identity mismatch")
            for source in evidence.sources:
                sources.append(MapSource(id=f"{stock}-{source.id}", title=source.title,
                                         url=source.url, stock_code=stock,
                                         published_on=str(source.published_at)
                                         if source.published_at else None,
                                         excerpt=source.excerpt[:4000]))
            gaps.extend(f"{stock}：{gap}" for gap in evidence.gaps)
        except Exception:
            logger.exception("Map company evidence failed: sector=%s stock=%s", code, stock)
            gaps.append(f"{stock}：公司资料未取得。")

    # Three concurrent companies, two batches; no unbounded all-market fetch.
    for start in range(0, len(selected), 3):
        await asyncio.gather(*(collect(stock) for stock in selected[start:start + 3]))
    return MapEvidence(sector_code=code, sector_name=detail.name, board_kind=detail.kind,
                       collected_at=datetime.now(UTC), members_as_of=members.fetched_at,
                       member_count=len(members.members), sampled_codes=selected,
                       sources=sorted(sources, key=lambda source: source.id), gaps=sorted(gaps))
