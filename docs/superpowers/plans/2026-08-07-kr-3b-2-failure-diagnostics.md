# KR-3B-2 Four-Layer Failure Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one unified KR-3 runtime assembler that returns either the existing complete four-layer envelope or a deterministic four-layer failure result without leaking partial business market data.

**Architecture:** Keep `assemble_complete_kline_business()` unchanged as the strict success-only primitive. Add `assemble_kline_business()` in the same focused runtime module as a thin preflight and classification boundary: expected data incompleteness becomes `KlineBusinessFailure`, while programmer wiring errors remain exceptions. Reuse existing `EvidenceEnvelope`, `KlineBusinessFailure`, and source diagnostics; do not add a new error framework or move files.

**Tech Stack:** Python 3.13, Pydantic v2 discriminated unions, Pytest, Ruff, Pyright.

## Global Constraints

- Do not add or change a production data source.
- Do not add dependencies, services, queues, API routes, frontend components, Agents, or LLM calls.
- Do not move code or documentation directories.
- Preserve `assemble_complete_kline_business()` and all current success-path behavior.
- `KlineBusinessFailure` must never carry `final_daily_bars`, minute bars, quotes, or provisional OHLCV.
- The failure result must diagnose `FINAL_DAILY`, `FINAL_MINUTE`, `LIVE_QUOTE`, and `PROVISIONAL` exactly once.
- Incomplete source evidence may retain cached items internally, but the unified assembler must not read those items to manufacture a successful layer.
- Wrong capability wiring, cross-symbol requests, naive `as_of`, and invalid market identity are programmer/contract errors and must continue to raise; they are not ordinary market-data failures.
- Stable layer error codes for this slice are:
  - `final_daily_evidence_incomplete`
  - `final_daily_adjustment_unavailable`
  - `final_daily_lineage_conflict`
  - `final_minute_evidence_incomplete`
  - `final_minute_missing`
  - `live_quote_evidence_incomplete`
  - `live_quote_cardinality_invalid`
  - `provisional_quote_dependency_incomplete`
  - `provisional_quote_dependency_invalid`
  - `provisional_quote_invalid`
- Error messages must be deterministic technical diagnostics. KR-5 will define user-facing copy; this slice must not invent frontend wording.
- Every code change requires an independent `code-reviewer` review before completion.
- Finish with `python scripts/check.py --full`; do not enter KR-4 or organization migration in this plan.

---

## File Structure

**Modify:**

- `src/data/kline_business_runtime.py` — unified preflight, deterministic layer diagnostics, success/failure dispatch.
- `src/data/__init__.py` — stable package export for `assemble_kline_business` while retaining the old export.
- `tests/test_data/test_kline_business_runtime.py` — runtime failure aggregation, success compatibility, and export contracts.
- `docs/02-requirements/KLINE_EVIDENCE_IMPLEMENTATION_PLAN.md` — mark KR-3B-2 complete and preserve the strategic pause before KR-4.
- `docs/03-modules/01-data-collection/README.md` — current data-module status.
- `docs/03-modules/01-data-collection/SPEC.md` — normative failure aggregation rule and test count.
- `docs/05-decisions/ADR-013-multi-source-evidence.md` — append the accepted runtime failure decision.
- `docs/06-departments/00-cross-cutting/HANDOVER.md` — global handoff and next strategic stop.
- `docs/06-departments/01-data/HANDOVER.md` — data handoff and do-not-retry guidance.
- `docs/06-departments/01-data/DEBT.md` — reduce TD-069 remaining principal to KR-4～6 without closing it.
- `docs/06-departments/02-debate-engine/DEBT.md` — record that KR-3 is ready for later consumption but remains disconnected by strategy.
- `docs/00-overview/ROADMAP.md` — replace KR-3B-2 next-step text with the validation-first strategic checkpoint.
- `docs/01-guides/HANDOVER.md` — update the next session entry point.
- `docs/learning/50-runtime-evidence-assembly.md` — extend the existing card with failure aggregation and a 3–5 minute exercise.

**Create:**

- `docs/04-changelog/logs/2026-08-07/2026-08-07.md` — implementation evidence, tests, review findings, and strategic stop.

No other file is in scope unless a failing reference check proves it still names KR-3B-2 as unfinished.

---

### Task 1: Convert incomplete source envelopes into four-layer failures

**Files:**

- Modify: `tests/test_data/test_kline_business_runtime.py`
- Modify: `src/data/kline_business_runtime.py`

**Interfaces:**

- Consumes: existing `EvidenceEnvelope`, `KlineBusinessEnvelope`, `KlineBusinessFailure`, `KlineBusinessLayer`, `KlineBusinessResult`, and `KlineLayerDiagnostic`.
- Produces:

```text
assemble_kline_business(
    *,
    symbol: str,
    market: MarketCode,
    as_of: datetime,
    trading_phase: TradingPhase,
    final_daily_bars: AdjustedKlineSeries | None,
    daily_snapshot_id: str | None,
    daily_evidence: EvidenceEnvelope,
    intraday_evidence: EvidenceEnvelope,
    quote_evidence: EvidenceEnvelope,
) -> KlineBusinessResult
```

- Keeps the full existing `assemble_complete_kline_business` signature and its `KlineBusinessEnvelope` return type exactly compatible.

- [ ] **Step 1: Import the result and diagnostic types in the runtime tests**

Change the test imports to include both assemblers and the failure types:

```python
from src.data.kline_business import (
    KlineBusinessFailure,
    KlineBusinessLayer,
    TradingPhase,
)
from src.data.kline_business_runtime import (
    assemble_complete_kline_business,
    assemble_kline_business,
)
```

- [ ] **Step 2: Add a deterministic helper for incomplete evidence fixtures**

Add this helper below `_quote_evidence()`:

```python
def _incomplete(
    envelope: EvidenceEnvelope,
    *,
    error_code: str = "upstream_request_failed",
) -> EvidenceEnvelope:
    failed_source = envelope.source_results[0]
    failed = failed_source.model_copy(
        update={
            "status": SourceStatus.FAILED,
            "items": [],
            "error_code": error_code,
            "error_message": "fixture upstream failed",
        }
    )
    return envelope.model_copy(
        update={
            "complete": False,
            "assessment": envelope.assessment.model_copy(
                update={
                    "complete": False,
                    "successful_upstream_ids": (
                        envelope.assessment.successful_upstream_ids
                        - {failed_source.upstream_id}
                    ),
                    "successful_source_ids": (
                        envelope.assessment.successful_source_ids
                        - {failed_source.source_id}
                    ),
                    "failed_source_ids": {failed_source.source_id},
                    "unusable_source_ids": {failed_source.source_id},
                    "missing_independent_upstreams": 1,
                }
            ),
            "source_results": [failed, *envelope.source_results[1:]],
        }
    )
```

The fixture deliberately leaves `envelope.items` untouched to prove cached business items cannot leak into a successful result.

- [ ] **Step 3: Write the single-layer failure tests**

Add a parameterized test with exact expected incomplete layers and codes:

```python
@pytest.mark.parametrize(
    ("failed_input", "expected"),
    [
        (
            "daily",
            {KlineBusinessLayer.FINAL_DAILY: "final_daily_evidence_incomplete"},
        ),
        (
            "intraday",
            {KlineBusinessLayer.FINAL_MINUTE: "final_minute_evidence_incomplete"},
        ),
        (
            "quote",
            {
                KlineBusinessLayer.LIVE_QUOTE: "live_quote_evidence_incomplete",
                KlineBusinessLayer.PROVISIONAL:
                    "provisional_quote_dependency_incomplete",
            },
        ),
    ],
)
def test_unified_assembler_returns_four_layer_failure_without_partial_data(
    failed_input: str,
    expected: dict[KlineBusinessLayer, str],
) -> None:
    evidence = {
        "daily": _daily_evidence(),
        "intraday": _intraday_evidence(),
        "quote": _quote_evidence(),
    }
    evidence[failed_input] = _incomplete(evidence[failed_input])

    result = assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=evidence["daily"],
        intraday_evidence=evidence["intraday"],
        quote_evidence=evidence["quote"],
    )

    assert isinstance(result, KlineBusinessFailure)
    diagnostics = {item.layer: item for item in result.layer_diagnostics}
    assert set(diagnostics) == set(KlineBusinessLayer)
    assert {
        layer: diagnostic.error_code
        for layer, diagnostic in diagnostics.items()
        if not diagnostic.complete
    } == expected
    assert set(result.error_codes) == set(expected.values())
    payload = result.model_dump()
    assert "final_daily_bars" not in payload
    assert "final_minute_bars" not in payload
    assert "live_quote" not in payload
    assert "provisional_session_bar" not in payload
```

- [ ] **Step 4: Run the new test and verify RED**

Run:

```powershell
python -m pytest tests/test_data/test_kline_business_runtime.py::test_unified_assembler_returns_four_layer_failure_without_partial_data -q
```

Expected: collection or import failure because `assemble_kline_business` does not exist.

- [ ] **Step 5: Implement evidence classification helpers**

In `src/data/kline_business_runtime.py`, add imports for the failure types and implement private helpers with these signatures:

```python
def _diagnostic_summary(evidence: EvidenceEnvelope) -> str:
    parts = sorted(
        f"{result.source_id}:{result.status.value}:"
        f"{result.error_code or 'no_error_code'}"
        for result in evidence.source_results
        if result.status not in {SourceStatus.SUCCESS_DATA, SourceStatus.SUCCESS_EMPTY}
    )
    return ",".join(parts) or "evidence assessment is incomplete"


def _diagnostic(
    *,
    layer: KlineBusinessLayer,
    complete: bool,
    upstream_ids: tuple[str, ...],
    error_code: str | None = None,
    error_message: str | None = None,
) -> KlineLayerDiagnostic:
    return KlineLayerDiagnostic(
        layer=layer,
        complete=complete,
        upstream_ids=tuple(sorted(upstream_ids)),
        error_code=error_code,
        error_message=error_message,
    )
```

Import `SourceStatus` only for deterministic diagnostic summarization. Do not pass raw exception messages into the compact business failure.

- [ ] **Step 6: Implement the incomplete-envelope branch**

Implement `assemble_kline_business()` so that it validates capability and request symbol first, creates four diagnostics in enum order, and returns `KlineBusinessFailure` whenever any input envelope is incomplete. Quote incompleteness must mark both `LIVE_QUOTE` and the dependent `PROVISIONAL` layer incomplete.

The returned failure must use:

```python
return KlineBusinessFailure(
    symbol=symbol,
    market=market,
    as_of=as_of,
    trading_phase=trading_phase,
    error_codes=tuple(
        dict.fromkeys(
            diagnostic.error_code
            for diagnostic in diagnostics
            if diagnostic.error_code is not None
        )
    ),
    layer_diagnostics=tuple(diagnostics),
)
```

Do not access `evidence.items` for an incomplete envelope.

- [ ] **Step 7: Run the runtime tests**

Run:

```powershell
python -m pytest tests/test_data/test_kline_business_runtime.py -q
```

Expected: all existing tests plus the new incomplete-envelope matrix pass.

- [ ] **Step 8: Commit Task 1**

```powershell
git add -- src/data/kline_business_runtime.py tests/test_data/test_kline_business_runtime.py
git commit -m "feat: merge incomplete K-line runtime diagnostics"
```

---

### Task 2: Classify derived layer failures without hiding contract bugs

**Files:**

- Modify: `tests/test_data/test_kline_business_runtime.py`
- Modify: `src/data/kline_business_runtime.py`

**Interfaces:**

- Consumes: `assemble_kline_business()` from Task 1.
- Produces: deterministic failures for missing adjusted daily data, lineage conflicts, missing final minutes, invalid quote cardinality, and invalid provisional OHLC.
- Preserves exceptions for wrong capability wiring and cross-symbol evidence requests.

- [ ] **Step 1: Add the derived failure matrix**

Add separate tests with explicit mutations and expected layer codes:

```python
def test_unified_assembler_reports_missing_adjusted_daily_series() -> None:
    result = assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=None,
        daily_snapshot_id=None,
        daily_evidence=_daily_evidence(),
        intraday_evidence=_intraday_evidence(),
        quote_evidence=_quote_evidence(),
    )
    assert isinstance(result, KlineBusinessFailure)
    assert result.error_codes == ("final_daily_adjustment_unavailable",)


def test_unified_assembler_reports_daily_snapshot_lineage_conflict() -> None:
    result = assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id="raw:000001:other-snapshot",
        daily_evidence=_daily_evidence(),
        intraday_evidence=_intraday_evidence(),
        quote_evidence=_quote_evidence(),
    )
    assert isinstance(result, KlineBusinessFailure)
    assert result.error_codes == ("final_daily_lineage_conflict",)
```

Add these exact tests for the remaining derived failures:

```python
def test_unified_assembler_reports_missing_final_minute() -> None:
    intraday = _intraday_evidence()
    provisional_items = [
        item.model_copy(update={"state": IntradayBarState.PROVISIONAL})
        for item in intraday.items
        if isinstance(item, IntradayBar)
    ]
    intraday = intraday.model_copy(update={"items": provisional_items})

    result = assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=_daily_evidence(),
        intraday_evidence=intraday,
        quote_evidence=_quote_evidence(),
    )

    assert isinstance(result, KlineBusinessFailure)
    assert result.error_codes == ("final_minute_missing",)


@pytest.mark.parametrize("cardinality", [0, 2])
def test_unified_assembler_reports_invalid_quote_cardinality(cardinality: int) -> None:
    quote = _quote_evidence()
    canonical = quote.items[0]
    quote = quote.model_copy(update={"items": [canonical] * cardinality})

    result = assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=_daily_evidence(),
        intraday_evidence=_intraday_evidence(),
        quote_evidence=quote,
    )

    assert isinstance(result, KlineBusinessFailure)
    assert result.error_codes == (
        "live_quote_cardinality_invalid",
        "provisional_quote_dependency_invalid",
    )


def test_unified_assembler_reports_invalid_provisional_quote() -> None:
    quote = _quote_evidence()
    canonical = quote.items[0].model_copy(update={"price": 11.0})
    quote = quote.model_copy(update={"items": [canonical]})

    result = assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=_daily_evidence(),
        intraday_evidence=_intraday_evidence(),
        quote_evidence=quote,
    )

    assert isinstance(result, KlineBusinessFailure)
    diagnostics = {item.layer: item for item in result.layer_diagnostics}
    assert diagnostics[KlineBusinessLayer.LIVE_QUOTE].complete is True
    assert diagnostics[KlineBusinessLayer.PROVISIONAL].error_code == (
        "provisional_quote_invalid"
    )
```

- [ ] **Step 2: Add contract-bug preservation tests**

Call the new unified assembler with a wrong capability envelope and with a request for `600000`. Use the existing `_final_daily_series()`, `_daily_evidence()`, `_intraday_evidence()`, and `_quote_evidence()` fixtures and assert the same `ValueError` messages already enforced by the strict success assembler:

```python
wrong_capability = _quote_evidence()
with pytest.raises(ValueError, match="runtime evidence capability"):
    assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=wrong_capability,
        intraday_evidence=_intraday_evidence(),
        quote_evidence=_quote_evidence(),
    )

other_symbol = _intraday_evidence()
other_symbol = other_symbol.model_copy(
    update={
        "request": other_symbol.request.model_copy(update={"stock_code": "600000"})
    }
)
with pytest.raises(ValueError, match="runtime evidence symbol"):
    assemble_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=_final_daily_series(),
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=_daily_evidence(),
        intraday_evidence=other_symbol,
        quote_evidence=_quote_evidence(),
    )
```

- [ ] **Step 3: Run the derived tests and verify RED**

Run:

```powershell
python -m pytest tests/test_data/test_kline_business_runtime.py -k "missing_adjusted or lineage_conflict or final_minute_missing or cardinality or provisional_quote or contract_bug" -q
```

Expected: the new cases fail because Task 1 only handles incomplete envelopes.

- [ ] **Step 4: Implement derived preflight classification**

Before calling the strict success assembler, calculate layer readiness without mutating the envelopes:

```python
final_daily_ready = (
    final_daily_bars is not None
    and daily_snapshot_id is not None
    and final_daily_bars.raw_snapshot_id == daily_snapshot_id
)
final_minutes = tuple(
    item
    for item in intraday_evidence.items
    if isinstance(item, IntradayBar) and item.state is IntradayBarState.FINAL
)
quotes = tuple(item for item in quote_evidence.items if isinstance(item, StockQuote))
```

Rules:

- Source-envelope incompleteness wins over derived errors for the same layer.
- `final_daily_bars is None` or `daily_snapshot_id is None` maps to `final_daily_adjustment_unavailable`.
- Non-matching non-null snapshot IDs map to `final_daily_lineage_conflict`.
- An otherwise complete intraday envelope with no final minute maps to `final_minute_missing`.
- Invalid quote cardinality marks `LIVE_QUOTE` and `PROVISIONAL` incomplete with separate dependency codes.
- Validate the single quote as `LiveRawQuote`; then attempt `ProvisionalSessionBar` construction. Catch only `pydantic.ValidationError` from these data conversions. Do not catch arbitrary `Exception` or the programmer-contract `ValueError` checks.
- Build diagnostics in `tuple(KlineBusinessLayer)` order so JSON and tests remain deterministic.

- [ ] **Step 5: Dispatch the all-complete branch to the existing strict assembler**

When all diagnostics are complete, use an assertion to narrow the optional values and call:

```python
assert final_daily_bars is not None
assert daily_snapshot_id is not None
return assemble_complete_kline_business(
    symbol=symbol,
    market=market,
    as_of=as_of,
    trading_phase=trading_phase,
    final_daily_bars=final_daily_bars,
    daily_snapshot_id=daily_snapshot_id,
    daily_evidence=daily_evidence,
    intraday_evidence=intraday_evidence,
    quote_evidence=quote_evidence,
)
```

Do not duplicate construction of `KlineBusinessEnvelope` in the new function.

- [ ] **Step 6: Run focused and combined regressions**

Run:

```powershell
python -m pytest tests/test_data/test_kline_business_runtime.py tests/test_data/test_kline_business_envelope.py -q
```

Expected: all tests pass; the old strict assembler still raises on its documented misuse cases.

- [ ] **Step 7: Commit Task 2**

```powershell
git add -- src/data/kline_business_runtime.py tests/test_data/test_kline_business_runtime.py
git commit -m "feat: classify K-line derived layer failures"
```

---

### Task 3: Publish the unified result boundary and synchronize project truth

**Files:**

- Modify: `src/data/__init__.py`
- Modify: `tests/test_data/test_kline_business_runtime.py`
- Modify all documentation files listed in the File Structure section.
- Create: `docs/04-changelog/logs/2026-08-07/2026-08-07.md`

**Interfaces:**

- Produces package export `src.data.assemble_kline_business`.
- Keeps package export `src.data.assemble_complete_kline_business` for strict/internal callers.
- Does not connect the result to debate, backend, frontend, risk, trader, or backtest.

- [ ] **Step 1: Add the package export contract test**

Extend the existing export test:

```python
def test_data_package_exports_complete_runtime_assembler() -> None:
    from src import data

    assert data.assemble_complete_kline_business is assemble_complete_kline_business
    assert data.assemble_kline_business is assemble_kline_business
```

- [ ] **Step 2: Run the export test and verify RED**

Run:

```powershell
python -m pytest tests/test_data/test_kline_business_runtime.py::test_data_package_exports_complete_runtime_assembler -q
```

Expected: failure because `src.data` does not export `assemble_kline_business`.

- [ ] **Step 3: Export the unified assembler**

Change the import to:

```python
from src.data.kline_business_runtime import (
    assemble_complete_kline_business,
    assemble_kline_business,
)
```

Add `"assemble_kline_business"` to `__all__` next to the strict assembler.

- [ ] **Step 4: Run the export and complete KR-3 regressions**

Run:

```powershell
python -m pytest tests/test_data/test_kline_business_runtime.py tests/test_data/test_kline_business_envelope.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Synchronize requirements, ADR, module docs, debt, and handoffs**

Make these exact state changes:

- Mark KR-3B-2 complete and state that KR-3 now yields a discriminated success/failure result.
- Keep TD-069 open; remaining principal is KR-4～6 and later industry evidence migration.
- State that strategy pauses automatic entry into KR-4 until the validation-first checkpoint is planned.
- State that no AI, API, frontend, risk, trading, or backtest consumer was added in this slice.
- Document all ten stable error codes from Global Constraints.
- Update references that still say “KR-3B-2 next” to “KR-3B-2 complete; validation-first checkpoint next.”
- Do not rewrite historical changelog entries or completed-session records; historical text remains historical evidence.

- [ ] **Step 6: Extend learning card 50**

Add sections explaining:

- why cached items inside an incomplete envelope cannot become partial success;
- why quote failure affects both `LIVE_QUOTE` and dependent `PROVISIONAL`;
- why programmer wiring errors remain exceptions;
- a “自己试试” command that mutates one envelope to `complete=False` and inspects all four diagnostics.

Link back to card 49 and forward to the next existing card only if one exists; do not create a speculative card 51.

- [ ] **Step 7: Create the 2026-08-07 work log**

Record:

- task scope and strategic pause;
- exact files changed;
- focused test counts;
- code-review findings and resolutions;
- full gate result;
- no push until the user asks.

- [ ] **Step 8: Run reference cleanup**

Run:

```powershell
rg -n "KR-3B-2|assemble_complete_kline_business|assemble_kline_business" docs src tests
```

Review every match. Update current-status references, preserve explicitly historical entries, and ensure there is no second assembler implementation or competing error-code table.

- [ ] **Step 9: Commit Task 3**

Stage explicit paths only, then commit:

```powershell
git add -- src/data/__init__.py tests/test_data/test_kline_business_runtime.py docs/00-overview/ROADMAP.md docs/01-guides/HANDOVER.md docs/02-requirements/KLINE_EVIDENCE_IMPLEMENTATION_PLAN.md docs/03-modules/01-data-collection/README.md docs/03-modules/01-data-collection/SPEC.md docs/04-changelog/logs/2026-08-07/2026-08-07.md docs/05-decisions/ADR-013-multi-source-evidence.md docs/06-departments/00-cross-cutting/HANDOVER.md docs/06-departments/01-data/HANDOVER.md docs/06-departments/01-data/DEBT.md docs/06-departments/02-debate-engine/DEBT.md docs/learning/50-runtime-evidence-assembly.md
git commit -m "docs: hand off KR-3 failure diagnostics"
```

---

### Task 4: Independent review and release gate

**Files:**

- Review all files changed by Tasks 1～3.
- Modify only files required to resolve findings.

**Interfaces:**

- Consumes: completed KR-3B-2 implementation and documentation.
- Produces: independently reviewed, fully gated atomic delivery ready for user review.

- [ ] **Step 1: Request independent code review**

Invoke the required `code-reviewer` with this scope:

```text
Review KR-3B-2 only. Verify deterministic error-code aggregation, all four layer diagnostics,
absence of partial business data, preservation of programmer exceptions, backward compatibility
of assemble_complete_kline_business, and no premature downstream integration.
```

- [ ] **Step 2: Apply valid findings with focused regression tests**

For every accepted finding:

1. add or adjust the smallest failing test;
2. run that exact test to verify RED;
3. apply the minimal fix;
4. run the focused runtime and envelope suites;
5. record the finding and resolution in the 2026-08-07 work log.

Reject a finding only with concrete code/test evidence and record the reason in the work log.

- [ ] **Step 3: Run static checks**

Run:

```powershell
ruff check src/data/kline_business_runtime.py src/data/__init__.py tests/test_data/test_kline_business_runtime.py
pyright src/data/kline_business_runtime.py src/data/__init__.py
```

Expected: zero errors.

- [ ] **Step 4: Run the complete project gate**

Run:

```powershell
python scripts/check.py --full
```

Expected: Ruff, Pyright, all non-slow Python tests, and frontend type-check pass. Existing third-party deprecation warnings may remain but no new warning is accepted.

- [ ] **Step 5: Verify clean scope and strategic stop**

Run:

```powershell
git status --short
git diff --check HEAD~3..HEAD
git log -3 --oneline
```

Confirm:

- no unrelated user files changed;
- no code or directory migration occurred;
- TD-069 remains open;
- current handoff points to the validation-first checkpoint, not automatic KR-4 implementation;
- the worktree is clean after the final commit.

- [ ] **Step 6: Commit review fixes if required**

If review produced changes:

```powershell
git status --short
# Copy only the concrete paths reported above into the next command.
git add -- src/data/kline_business_runtime.py tests/test_data/test_kline_business_runtime.py docs/04-changelog/logs/2026-08-07/2026-08-07.md
git commit -m "fix: harden K-line failure aggregation"
```

If the review changed a different already-in-scope documentation file, add that exact path as well. If there were no findings, do not create an empty commit.

- [ ] **Step 7: Stop for user review**

Report focused tests, full gate results, review outcome, commits, and the explicit strategic stop. Do not push and do not start O0/O1 organization work until the user reviews KR-3B-2.
