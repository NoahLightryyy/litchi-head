"""Generated maps must never fabricate provenance or lose previous versions."""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import sector_maps as maps
from backend.routers import sector_maps as route
from backend.sector_maps import MapEvidence, MapGraph, MapStore, validate_evidence
from src.data.board_store import BoardSnapshotStore
from src.data.providers.eastmoney_boards import BoardDetailSnapshot, BoardMembersSnapshot


def evidence():
    return MapEvidence(sector_code="BK1325", sector_name="半导体材料", board_kind="industry",
                       collected_at=datetime.now(UTC), members_as_of=datetime.now(UTC),
                       member_count=32, sampled_codes=["300666"], gaps=["仅覆盖一家公司"],
                       sources=[dict(id="report", title="年度报告",
                                     url="https://example.org/report", stock_code="300666",
                                     excerpt="公司生产用于半导体制造的电子材料，报告期内扩建生产设施。")])


def graph():
    return MapGraph(map_kind="industry_chain", scope="仅依据样本公司披露资料",
                    nodes=[dict(id="materials", label="电子材料", explanation="半导体制造材料",
                                citations=[dict(source_id="report",
                                                quote="用于半导体制造的电子材料")])],
                    edges=[])


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.state.limiter = route.limiter
    app.include_router(route.router)
    route._busy.clear()
    with patch.object(route, "store", MapStore(tmp_path / "maps.db")):
        yield TestClient(app)
    route._busy.clear()


def test_versions_persist_and_bad_references_cannot_replace_them(tmp_path):
    store = MapStore(tmp_path / "maps.db")
    first = store.save(graph(), evidence(), "test-model")
    changed = graph()
    changed.scope = "新资料范围"
    second = store.save(changed, evidence(), "test-model")
    reopened = MapStore(tmp_path / "maps.db")
    assert reopened.read("BK1325").current == second
    assert reopened.read("BK1325", 1).current == first
    changed.nodes[0].citations[0].quote = "捏造的原文不会出现在来源里"
    with pytest.raises(ValueError):
        store.save(changed, evidence(), "test-model")
    assert reopened.read("BK1325").current == second
    assert len(reopened.read("BK1325").history) == 2


@pytest.mark.parametrize("invalid", ["source", "quote", "kind"])
def test_reject_invalid_evidence(invalid):
    candidate = graph()
    if invalid == "source":
        candidate.nodes[0].citations[0].source_id = "invented"
    elif invalid == "quote":
        candidate.nodes[0].citations[0].quote = "这段原文并不存在于资料中"
    else:
        candidate.map_kind = "market_structure"
    with pytest.raises(ValueError):
        validate_evidence(candidate, evidence())


def test_reject_duplicate_and_dangling_graph_nodes():
    raw = graph().model_dump()
    raw["nodes"].append(raw["nodes"][0])
    with pytest.raises(ValidationError):
        MapGraph.model_validate(raw)
    raw = graph().model_dump()
    raw["edges"] = [dict(source="materials", target="missing", explanation="不存在的节点",
                         citations=raw["nodes"][0]["citations"])]
    with pytest.raises(ValidationError):
        MapGraph.model_validate(raw)


def test_read_does_not_call_ai_and_unchanged_evidence_skips_regeneration(client):
    supplied = evidence()
    ai = AsyncMock(return_value=graph())
    with patch.object(route, "collect_map_evidence", AsyncMock(return_value=supplied)), \
         patch.object(route.llm_service, "invoke_structured", ai):
        assert client.get("/api/market/sector/BK1325/map").json()["current"] is None
        ai.assert_not_called()
        first = client.post("/api/market/sector/BK1325/map")
        assert first.status_code == 200, first.text
        supplied.collected_at += timedelta(hours=1)
        supplied.members_as_of += timedelta(hours=1)
        second = client.post("/api/market/sector/BK1325/map")
        assert second.status_code == 200
        assert ai.await_count == 1
        assert second.json()["current"]["review_status"] == "ai_unreviewed"
        assert not second.json()["automatic_updates"]


def test_source_and_ai_failure_preserve_previous_map(client):
    route.store.save(graph(), evidence(), "test-model")
    with patch.object(route, "collect_map_evidence", AsyncMock(side_effect=ValueError("offline"))):
        assert client.post("/api/market/sector/BK1325/map").status_code == 503
    supplied = evidence()
    supplied.sources[0].excerpt += "新披露"
    with patch.object(route, "collect_map_evidence", AsyncMock(return_value=supplied)), \
         patch.object(route.llm_service, "invoke_structured", AsyncMock(side_effect=TimeoutError)):
        assert client.post("/api/market/sector/BK1325/map").status_code == 504
    stored = client.get("/api/market/sector/BK1325/map").json()
    assert len(stored["history"]) == 1
    assert stored["current"]["version"] == 1


def test_unknown_board_invalid_path_and_busy(client):
    assert client.post("/api/market/sector/not-a-board/map").status_code == 422
    with patch.object(route, "collect_map_evidence", AsyncMock(side_effect=LookupError)):
        assert client.post("/api/market/sector/BK1325/map").status_code == 404
    route._busy.add("BK1325")
    assert client.post("/api/market/sector/BK1325/map").status_code == 429


def test_storage_corruption_is_visible(client):
    route.store.save(graph(), evidence(), "test-model")
    db = route.store.connect()
    with db:
        db.execute("UPDATE versions SET digest='corrupted'")
    db.close()
    assert client.get("/api/market/sector/BK1325/map").status_code == 503


async def test_historical_members_are_explicit_and_company_failures_are_partial(tmp_path):
    from backend.company_research import CompanyEvidence

    now = datetime.now(UTC)
    snapshot = BoardMembersSnapshot(board_code="BK1325", kind="industry", fetched_at=now,
                                   members=tuple(dict(code=code, name=code, price=None,
                                                      change_pct=None, fund_flow=None, as_of=now)
                                                 for code in ("300666", "002119")))
    store = BoardSnapshotStore(tmp_path / "boards.db")
    store.record_success(snapshot)
    disclosure = CompanyEvidence(stock_code="002119", company_name="样本公司", fetched_at=now,
                                 sources=[dict(id="profile", title="公司主营",
                                               url="https://example.org/company",
                                               excerpt="公司生产半导体封装引线框架材料。")],
                                 gaps=[])
    with patch.object(maps.board_snapshots, "store", store), \
         patch.object(maps.board_snapshots, "fetch_detail", return_value=BoardDetailSnapshot(
             code="BK1325", name="半导体材料", kind="industry")), \
         patch.object(maps.board_snapshots, "fetch_members", side_effect=TimeoutError), \
         patch.object(maps, "fetch_evidence", AsyncMock(side_effect=[disclosure, ValueError])):
        result = await maps.collect_map_evidence("BK1325")
    assert result.sampled_codes == ["002119", "300666"]
    assert len(result.sources) == 1
    assert any("历史成员快照" in gap for gap in result.gaps)
    assert any("300666：公司资料未取得" in gap for gap in result.gaps)
