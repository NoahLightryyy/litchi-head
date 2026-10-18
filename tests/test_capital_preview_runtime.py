from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.capital_preview import VerifiedExecutionContext, calculate_preview
from backend.policy_capital_contract import (
    Evidence,
    EvidencePackage,
    ExecutionRequest,
    FeeSchedule,
    TradingRule,
)
from backend.routers.capital_preview import create_router


def test_missing_fields_are_blocked():
    request = ExecutionRequest(
        evidence_package_id="p",
        instrument_kind="stock",
        symbol="688012",
        market="SH",
        cash_available_cny=None,
        user_budget_cny=None,
        limit_price_cny=None,
        quote_at=None,
        permission_confirmed=None,
        rules=None,
        fees=None,
    )
    result = calculate_preview(request, now=datetime.now(UTC))
    assert result.status == "blocked"
    assert result.quantity is result.estimated_cost is result.remaining_cash is None
    assert result.gaps


NOW = datetime(2026, 10, 18, 10, tzinfo=UTC)


def fixture(kind="stock"):
    symbol = "688012" if kind == "stock" else "512480"
    rule = TradingRule(
        evidence_id="r",
        version="test",
        effective_from=date(2026, 7, 6),
        effective_until=None,
        min_quantity=200 if kind == "stock" else 100,
        quantity_step=1 if kind == "stock" else 100,
        max_quantity=100000,
        price_tick_cny=Decimal(".01") if kind == "stock" else Decimal(".001"),
    )
    fees = FeeSchedule(
        version="test",
        source_reference="broker-test-proof",
        verified_at=NOW,
        commission_rate=Decimal(".0003"),
        minimum_commission_cny=Decimal("5"),
        additional_rate=Decimal("0"),
        additional_fixed_cny=Decimal("0"),
        includes_all_applicable_costs=True,
    )
    evidence = Evidence(
        id="r",
        canonical_document_id="rule-test",
        url="https://www.sse.com.cn/rules",
        publisher="SSE",
        role="primary",
        title="Test rule evidence",
        locator="section",
        authored_date=None,
        published_date=date(2026, 7, 6),
        effective_date=date(2026, 7, 6),
        effective_date_status="stated",
        retrieved_at=NOW,
        snapshot_sha256=None,
        summary="Test only",
    )
    package = EvidencePackage(
        package_id="p",
        subject_kind=kind,
        subject_id=symbol,
        status="verified_scope",
        evidence=[evidence],
        claims=[],
        holdings=[],
        gaps=[],
    )
    request = ExecutionRequest(
        evidence_package_id="p",
        instrument_kind=kind,
        symbol=symbol,
        market="SH",
        cash_available_cny=Decimal("10000"),
        user_budget_cny=Decimal("1000"),
        limit_price_cny=Decimal("1"),
        quote_at=NOW,
        permission_confirmed=True,
        rules=rule,
        fees=fees,
    )
    context = VerifiedExecutionContext(
        package,
        symbol,
        "SH",
        kind,
        rule,
        fees,
        "permission-proof",
        Decimal("10000"),
        "cash-proof",
        NOW,
        NOW + timedelta(minutes=2),
        NOW,
        timedelta(minutes=1),
    )
    return request, context


def test_star_increment_and_etf_lots():
    request, context = fixture()
    result = calculate_preview(request, context, now=NOW)
    assert (result.quantity, result.estimated_cost, result.remaining_cash) == (
        995,
        Decimal("1000"),
        Decimal("9000"),
    )
    request, context = fixture("etf")
    assert calculate_preview(request, context, now=NOW).quantity == 900


@pytest.mark.parametrize(
    "change",
    [
        {"cash_available_cny": None},
        {"user_budget_cny": None},
        {"limit_price_cny": None},
        {"quote_at": None},
        {"permission_confirmed": False},
        {"rules": None},
        {"fees": None},
        {"symbol": "600000"},
        {"market": "SZ"},
        {"evidence_package_id": "other"},
        {"quote_at": NOW + timedelta(seconds=1)},
        {"quote_at": NOW - timedelta(hours=1)},
        {"limit_price_cny": Decimal("1.001")},
        {"user_budget_cny": Decimal("204.99")},
        {"limit_price_cny": Decimal("1e1000")},
        {"cash_available_cny": Decimal("1e1000")},
    ],
)
def test_blocked_has_no_precision(change):
    request, context = fixture()
    result = calculate_preview(request.model_copy(update=change), context, now=NOW)
    assert result.status == "blocked"
    assert result.quantity is result.estimated_cost is result.remaining_cash is None


def test_cannot_forge_fees_or_permission():
    request, context = fixture()
    forged = request.model_copy(
        update={"fees": context.fees.model_copy(update={"minimum_commission_cny": Decimal("0")})}
    )
    assert calculate_preview(forged, context, now=NOW).status == "blocked"
    assert calculate_preview(request, now=NOW).status == "blocked"
    assert (
        calculate_preview(
            request, replace(context, permission_evidence_reference=""), now=NOW
        ).status
        == "blocked"
    )


def test_invalid_rule_and_attestation_dates():
    request, context = fixture()
    for rule in [
        context.rules.model_copy(update={"effective_from": date(2027, 1, 1)}),
        context.rules.model_copy(update={"effective_until": date(2026, 10, 17)}),
    ]:
        assert (
            calculate_preview(
                request.model_copy(update={"rules": rule}), replace(context, rules=rule), now=NOW
            ).status
            == "blocked"
        )
    assert (
        calculate_preview(
            request, replace(context, valid_until=NOW - timedelta(seconds=1)), now=NOW
        ).status
        == "blocked"
    )
    assert (
        calculate_preview(request, replace(context, max_quote_age=timedelta(0)), now=NOW).status
        == "blocked"
    )


def test_rounding_and_exact_minimum_and_cap():
    request, context = fixture()
    fees = context.fees.model_copy(
        update={"commission_rate": Decimal(".00001"), "minimum_commission_cny": Decimal("0")}
    )
    request = request.model_copy(update={"fees": fees, "user_budget_cny": Decimal("200.01")})
    result = calculate_preview(request, replace(context, fees=fees), now=NOW)
    assert result.quantity == 200
    assert result.estimated_cost == Decimal("200.01")
    rule = context.rules.model_copy(update={"max_quantity": 202})
    result = calculate_preview(
        request.model_copy(update={"rules": rule, "user_budget_cny": Decimal("1000")}),
        replace(context, fees=fees, rules=rule),
        now=NOW,
    )
    assert result.quantity == 202


def client(resolver=None):
    app = FastAPI()
    app.include_router(create_router(resolver))
    return TestClient(app)


def test_http_blocked_and_validation_errors():
    request, _ = fixture()
    api = client()
    response = api.post("/api/research/execution-preview", json=request.model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["quantity"] is None
    for change in [
        {"fees": {"commission_rate": "2"}},
        {"limit_price_cny": "NaN"},
        {"cash_available_cny": "Infinity"},
        {"instrument_kind": "sector"},
    ]:
        response = api.post(
            "/api/research/execution-preview", json={**request.model_dump(mode="json"), **change}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert response.json()["retryable"] is False


def test_http_dependency_failure():
    def failure(_):
        raise RuntimeError("test failure")

    request, _ = fixture()
    response = client(failure).post(
        "/api/research/execution-preview", json=request.model_dump(mode="json")
    )
    assert response.status_code == 503
    assert response.json()["code"] == "SOURCE_UNAVAILABLE"


def test_http_evidence_package_lookup_and_identity():
    request, context = fixture()
    app = FastAPI()
    app.include_router(create_router(package_resolver=lambda _: None))
    response = TestClient(app).post(
        "/api/research/execution-preview", json=request.model_dump(mode="json")
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PACKAGE_NOT_FOUND"
    app = FastAPI()
    app.include_router(create_router(package_resolver=lambda _: context.package))
    response = TestClient(app).post(
        "/api/research/execution-preview", json=request.model_dump(mode="json")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    response = TestClient(app).post(
        "/api/research/execution-preview",
        json={**request.model_dump(mode="json"), "symbol": "600000"},
    )
    assert response.json()["status"] == "blocked"
    assert "不匹配" in response.json()["gaps"][0]


def test_naive_server_dates_and_extreme_tick_block():
    request, context = fixture()
    assert calculate_preview(request, context, now=NOW.replace(tzinfo=None)).status == "blocked"
    assert (
        calculate_preview(
            request, replace(context, verified_at=NOW.replace(tzinfo=None)), now=NOW
        ).status
        == "blocked"
    )
    tick_rule = context.rules.model_copy(update={"price_tick_cny": Decimal("1e-1000")})
    assert (
        calculate_preview(
            request.model_copy(update={"rules": tick_rule}),
            replace(context, rules=tick_rule),
            now=NOW,
        ).status
        == "blocked"
    )


def test_client_fee_bounds_and_no_rule_evidence():
    request, context = fixture()
    from pydantic import ValidationError

    for rate in ["-0.1", "1.01"]:
        with pytest.raises(ValidationError):
            FeeSchedule.model_validate({**context.fees.model_dump(), "commission_rate": rate})
    missing_evidence = context.package.model_copy(update={"evidence": []})
    assert (
        calculate_preview(request, replace(context, package=missing_evidence), now=NOW).status
        == "blocked"
    )
