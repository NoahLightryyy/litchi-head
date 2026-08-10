# E0 Validation-First Checkpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, point-in-time E0 benchmark that freezes 100 historical A-share decisions, runs A0/A1/B0/B1/B3 against identical evidence, and produces one immutable full-denominator comparison report before KR-4 may resume.

**Architecture:** Add a focused `src/backtest/e0/` package rather than extending the legacy trade-replay engine into an experiment framework. The package owns immutable contracts, deterministic sampling, frozen-evidence runners, point-in-time labels, metrics, adjudication, and atomic artifacts; production Agents and Prompts remain unchanged. A real run requires explicit versioned regime, fee, position, confidence-bucket, code, model, and prompt configuration; absent configuration or integrity failure aborts the experiment.

**Tech Stack:** Python 3.13, Pydantic v2 frozen models, `Decimal`, asyncio, existing DeepSeek `llm_service`, existing `DebateOrchestrator`, existing K-line audit/adjustment contracts, Pytest, Ruff, Pyright.

## Global Constraints

- Do not add or change a production data source, dependency, API route, frontend component, Agent, department, queue, or service.
- Do not modify production Agent prompts, weights, risk defaults, or trading defaults.
- Do not enter KR-4, KR-5, KR-6, E1, broker integration, automatic order placement, short selling, or a general experiment platform.
- The official E0 sample count is exactly 100: 25 `UP`, 25 `DOWN`, 25 `SIDEWAYS`, and 25 `HIGH_VOLATILITY`; one symbol appears at most twice and one trade date at most five times.
- The primary horizon is exactly five trading days. One-day and twenty-day labels are auxiliary and may not replace it after results are visible.
- Runner IDs are exactly `A0`, `A1`, `B0`, `B1`, and `B3`; all are long-or-cash only.
- A0 and A1 use the same configured DeepSeek model, evidence snapshot, decision question, output contract, and five-day target. A1 must not receive A0 messages or output.
- `COMPLETE`, `ABSTAIN`, `FAILED`, and `TIMEOUT` records all remain in the denominator. No runner may answer for another runner.
- Future prices and labels are inaccessible to runners. Manifest, sample, evidence, decision, and label hashes are verified before reporting.
- A real run has no implicit `RegimePolicy`, `FeeProfile`, position profile, high-confidence threshold, model ID, Prompt version, code commit, or random seed. Missing values fail before runner execution.
- Tests use explicit synthetic fixtures only. The real 100-sample/LLM run is manual, is not placed in CI, and may not rewrite project conclusions automatically.
- Terminal experiment artifacts are append-only. Existing terminal data cannot be overwritten; interruption resumes only from validated frozen records.
- E0 results may only be `INVALID`, `STOP_AND_ABLATE`, `EXPAND_SAMPLE`, or `INSUFFICIENT_EVIDENCE`; they do not establish real-money performance.
- Every production-code task receives independent spec and quality review. Finish with `python scripts/check.py --full` and do not push unless the user asks.

---

## File Structure

**Create package:**

- `src/backtest/e0/__init__.py` — stable public E0 surface only.
- `src/backtest/e0/models.py` — frozen experiment, sample, decision, label, metric, report, and adjudication contracts.
- `src/backtest/e0/hashing.py` — canonical JSON and SHA-256 helpers shared by all E0 artifacts.
- `src/backtest/e0/store.py` — immutable experiment directory, atomic JSON/JSONL writes, integrity verification, and resume state.
- `src/backtest/e0/sampling.py` — explicit `RegimePolicy` classification and deterministic 25×4 manifest selection.
- `src/backtest/e0/runners.py` — runner protocol, B0/B1/B3, frozen evidence collector, A0 adapter, and A1 DeepSeek adapter.
- `src/backtest/e0/labeling.py` — point-in-time 1/5/20-day labels, execution constraints, and explicit A-share fees.
- `src/backtest/e0/metrics.py` — full-denominator paired metrics, ECE, stability audit, and report aggregation.
- `src/backtest/e0/adjudication.py` — pure E0 validity and decision truth table.
- `src/backtest/e0/engine.py` — orchestration, timeout/status mapping, idempotent resume, labeling, and report publication.
- `src/backtest/e0/reporting.py` — deterministic `report.json` and single human `report.md` renderer.
- `scripts/run_e0.py` — `freeze`, `dry-run`, `run`, `label`, `report`, and `verify` CLI.

**Create tests:**

- `tests/test_backtest/e0/test_models.py`
- `tests/test_backtest/e0/test_store.py`
- `tests/test_backtest/e0/test_sampling.py`
- `tests/test_backtest/e0/test_runners.py`
- `tests/test_backtest/e0/test_labeling.py`
- `tests/test_backtest/e0/test_metrics.py`
- `tests/test_backtest/e0/test_adjudication.py`
- `tests/test_backtest/e0/test_engine.py`
- `tests/test_scripts/test_run_e0.py`

**Modify:**

- `src/backtest/__init__.py` — export only the approved top-level E0 entry types/functions.
- `src/debate/trust.py` — expose the existing Brier/calibration arithmetic as pure helpers without changing `TrustTracker` behavior.
- `tests/test_debate/test_trust.py` — prove helper equivalence with current trust metrics.
- `README.md`, `docs/00-overview/ROADMAP.md`, `docs/01-guides/HANDOVER.md`, `docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md`, `docs/03-modules/07-backtesting/README.md`, `docs/03-modules/07-backtesting/SPEC.md`, `docs/05-decisions/ADR-013-multi-source-evidence.md`, `docs/06-departments/00-cross-cutting/HANDOVER.md`, `docs/06-departments/07-backtesting/HANDOVER.md`, `docs/06-departments/07-backtesting/DEBT.md`, `docs/learning/README.md` — synchronize implementation truth without claiming E0 results.
- `docs/learning/51-closed-book-decision-evaluation.md` — explain frozen manifests, label blindness, complete denominators, and paired comparisons.
- `docs/04-changelog/logs/2026-08-10/2026-08-10.md` — record implementation, reviews, gates, and the manual-run stop.

No `data/benchmarks/e0/` artifact is committed. Tests write under `tmp_path`; real runs write to an explicit `--root` path whose final directory is `<root>/<experiment_id>/`.

---

### Task 1: Freeze the E0 domain contract and canonical identities

**Files:**

- Create: `src/backtest/e0/models.py`
- Create: `src/backtest/e0/hashing.py`
- Create: `tests/test_backtest/e0/test_models.py`

**Interfaces:**

- Produces enums `MarketRegime`, `RunnerId`, `DecisionAction`, `RunnerStatus`, `ExperimentStatus`, and `E0Verdict`.
- Produces frozen models `RegimePolicy`, `FeeProfile`, `PositionProfile`, `ConfidencePolicy`, `A0RunnerConfig`, `CandidateSnapshot`, `FrozenEvidence`, `E0Sample`, `E0Manifest`, `RunnerContext`, `RunnerDecision`, `DecisionRecord`, `HorizonLabel`, `LabelRecord`, `RunnerMetrics`, `PairwiseMetrics`, `StabilityMetrics`, `E0IntegrityReport`, `E0Adjudication`, and `E0Report`.
- Produces `canonical_json(value: BaseModel | Mapping[str, object] | Sequence[object]) -> str` and `sha256_identity(prefix: str, value: object) -> str`.

- [ ] **Step 1: Write the canonical hashing RED tests**

```python
def test_canonical_identity_ignores_mapping_order() -> None:
    left = sha256_identity("manifest", {"b": 2, "a": 1})
    right = sha256_identity("manifest", {"a": 1, "b": 2})
    assert left == right
    assert left.startswith("manifest:sha256:")


def test_canonical_json_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"value": float("nan")})
```

- [ ] **Step 2: Run the hashing tests and verify RED**

Run: `python -m pytest tests/test_backtest/e0/test_models.py -q`

Expected: collection failure because `src.backtest.e0` does not exist.

- [ ] **Step 3: Implement deterministic JSON identities**

Use `model_dump(mode="json")`, `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`, UTF-8, and `hashlib.sha256`. Reject an empty prefix.

- [ ] **Step 4: Write the frozen-contract RED tests**

Cover these exact invariants:

```python
def test_real_manifest_requires_every_explicit_policy() -> None:
    with pytest.raises(ValidationError):
        E0Manifest(
            experiment_id="e0-missing-policy",
            created_at=AS_OF,
            code_commit="abc1234",
            model_id="deepseek-chat",
            a0_prompt_version="production:abc1234",
            a1_prompt_version="e0-single-agent:v1",
            random_seed=20260810,
            samples=(),
        )


def test_decision_record_is_deeply_frozen() -> None:
    record = _decision_record()
    with pytest.raises(ValidationError):
        record.action = DecisionAction.CASH
```

Also test timezone-aware timestamps, SHA-256 evidence hashes, confidence in `[0, 1]`, `LONG` requiring the configured position fraction, non-`COMPLETE` records carrying a stable error code, and uniqueness of `(sample_id, runner_id, repetition)`.

- [ ] **Step 5: Implement the exact configuration models**

Use no numeric defaults on these policy fields:

```python
class RegimePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = Field(min_length=1)
    lookback_trading_days: int = Field(ge=20)
    trend_return_threshold: Decimal = Field(gt=0)
    sideways_abs_return_max: Decimal = Field(ge=0)
    high_volatility_threshold: Decimal = Field(gt=0)


class FeeProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = Field(min_length=1)
    buy_commission_rate: Decimal = Field(ge=0)
    sell_commission_rate: Decimal = Field(ge=0)
    minimum_commission: Decimal = Field(ge=0)
    sell_stamp_tax_rate: Decimal = Field(ge=0)
    transfer_fee_rate: Decimal = Field(ge=0)
    slippage_rate: Decimal = Field(ge=0)


class PositionProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = Field(min_length=1)
    initial_capital: Decimal = Field(gt=0)
    long_fraction: Decimal = Field(gt=0, le=1)


class ConfidencePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = Field(min_length=1)
    high_confidence_threshold: Decimal = Field(gt=0, le=1)
    ece_bucket_edges: tuple[Decimal, ...]
    expansion_sample_count: int = Field(ge=300, le=500)
```

`A0RunnerConfig` freezes the five existing feature flags (`enable_risk`, `enable_trader`, `enable_reflection`, `enable_trust`, `enable_mirror`) and its version. `E0Manifest` contains all four policies, A0 configuration, one exact `decision_question`, exactly five runner IDs, primary horizon `5`, auxiliary horizons `(1, 20)`, candidate-universe hash, replacement order, code/model/Prompt versions, random seed, and exactly 100 final samples in real mode. Add `fixture_mode: bool = False`; only `fixture_mode=True` permits fewer than 100 samples for deterministic tests.

`CandidateSnapshot` owns historical membership proof and pre-decision regime inputs. `FrozenEvidence` owns the validated decision-time quote, completed K-lines, news, financials, industry, sentiment, evidence snapshot ID/hash, and `as_of`; it has no future-bar or label field. `RunnerContext` owns experiment/sample/runner/repetition identities, manifest position fraction, frozen model/question/Prompt versions, and timeout. `RunnerDecision` owns only action, position fraction, raw confidence, stable reason/error code, raw output hash, Token counts, model cost, and runner-reported latency. `E0IntegrityReport` and `E0Adjudication` carry machine-readable checks/reasons rather than prose-only status.

- [ ] **Step 6: Run model tests and static checks**

Run:

```powershell
python -m pytest tests/test_backtest/e0/test_models.py -q
ruff check src/backtest/e0/models.py src/backtest/e0/hashing.py tests/test_backtest/e0/test_models.py
pyright src/backtest/e0/models.py src/backtest/e0/hashing.py
```

- [ ] **Step 7: Commit Task 1**

```powershell
git add -- src/backtest/e0/models.py src/backtest/e0/hashing.py tests/test_backtest/e0/test_models.py
git commit -m "feat: define immutable E0 benchmark contracts"
```

---

### Task 2: Persist an immutable manifest and resumable artifact ledger

**Files:**

- Create: `src/backtest/e0/store.py`
- Create: `tests/test_backtest/e0/test_store.py`

**Interfaces:**

- Produces `E0ArtifactStore(root: Path)`.
- Produces `create(manifest: E0Manifest) -> None`, `load_manifest() -> E0Manifest`, `append_decision(record: DecisionRecord) -> None`, `append_label(record: LabelRecord) -> None`, `publish_report(report: E0Report, markdown: str) -> None`, `completed_decision_keys() -> frozenset[tuple[str, RunnerId, int]]`, and `verify() -> E0IntegrityReport`.
- Defines stable exceptions `E0StoreError`, `E0IntegrityError`, and `E0TerminalOverwriteError`.

- [ ] **Step 1: Write RED tests for creation, atomic publication, and terminal overwrite**

```python
def test_create_publishes_exact_manifest_and_hash(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "exp")
    store.create(_manifest())
    assert store.load_manifest() == _manifest()
    assert (tmp_path / "exp" / "manifest.sha256").read_text().startswith("manifest:sha256:")


def test_terminal_report_cannot_be_overwritten(tmp_path: Path) -> None:
    store = _store_with_terminal_report(tmp_path)
    with pytest.raises(E0TerminalOverwriteError):
        store.publish_report(_different_report(), "different")
```

Also inject `os.replace` failure and prove neither a partial target nor a false terminal marker exists.

- [ ] **Step 2: Run store tests and verify RED**

Run: `python -m pytest tests/test_backtest/e0/test_store.py -q`

- [ ] **Step 3: Implement atomic JSON/JSONL publication**

Write into the target directory using `tempfile.NamedTemporaryFile(delete=False, dir=target.parent)`, flush, `os.fsync`, close, then `os.replace`. Each JSONL record includes `record_hash`; on append, rewrite the validated full file atomically rather than exposing a partial line. Never catch arbitrary exceptions as success.

- [ ] **Step 4: Write RED tests for tampering and idempotent resume**

Cover manifest byte tampering, decision hash tampering, deleted failed decision, duplicate key with different content, label published before all decisions, report published before all labels, and identical decision replay as a no-op.

- [ ] **Step 5: Implement integrity and resume rules**

`verify()` recomputes every file/record hash, checks all manifest sample IDs, checks the exact full denominator, rejects labels whose `evidence_snapshot_id` differs from the sample, and reports missing decision/label keys without manufacturing records. `append_decision()` accepts byte-equivalent replay and rejects conflicting replay.

- [ ] **Step 6: Run store tests and commit**

```powershell
python -m pytest tests/test_backtest/e0/test_store.py -q
git add -- src/backtest/e0/store.py tests/test_backtest/e0/test_store.py
git commit -m "feat: add immutable E0 artifact ledger"
```

---

### Task 3: Freeze the deterministic 25×4 historical sample manifest

**Files:**

- Create: `src/backtest/e0/sampling.py`
- Create: `tests/test_backtest/e0/test_sampling.py`

**Interfaces:**

- Consumes prebuilt `CandidateSnapshot` rows containing historical CSI 300 membership proof, decision-time evidence identity, and only pre-decision regime inputs. This task does not fetch a new source.
- Produces `classify_regime(candidate: CandidateSnapshot, policy: RegimePolicy) -> MarketRegime`.
- Produces `freeze_samples(candidates: Sequence[CandidateSnapshot], *, experiment_id: str, policies: ..., random_seed: int, versions: ...) -> E0Manifest`.

- [ ] **Step 1: Write regime classification RED tests**

Lock this exact precedence so one sample has one regime:

1. annualized realized volatility `>= high_volatility_threshold` → `HIGH_VOLATILITY`;
2. lookback return `>= trend_return_threshold` → `UP`;
3. lookback return `<= -trend_return_threshold` → `DOWN`;
4. absolute lookback return `<= sideways_abs_return_max` → `SIDEWAYS`;
5. otherwise reject the candidate as `regime_unclassified`.

The candidate stores the exact ordered return window and its hash. The classifier recalculates the return and sample-standard-deviation annualized volatility with `sqrt(252)`; it does not trust caller-supplied labels.

- [ ] **Step 2: Run classification tests and verify RED**

Run: `python -m pytest tests/test_backtest/e0/test_sampling.py -q`

- [ ] **Step 3: Implement classification with `Decimal` inputs and deterministic float conversion only at square root**

Reject a window shorter than `lookback_trading_days`, dates at or after `decision_at`, non-positive prices, duplicate dates, and identity mismatches.

- [ ] **Step 4: Write manifest-selection RED tests**

Cover exact 25-per-regime allocation, symbol cap 2, date cap 5, deterministic seed, candidate-universe hash, all exclusions with stable codes, pre-registered replacement order, and failure when any regime cannot reach 25.

- [ ] **Step 5: Implement deterministic selection**

Sort candidates by `candidate_id`, apply `random.Random(random_seed).shuffle`, take candidates while enforcing caps, and keep all unused valid candidates in manifest `replacement_order`. Never select a replacement after runner output is visible; replacement is allowed only for manifest integrity invalidation and always takes the next matching pre-registered regime.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m pytest tests/test_backtest/e0/test_sampling.py -q
git add -- src/backtest/e0/sampling.py tests/test_backtest/e0/test_sampling.py
git commit -m "feat: freeze deterministic E0 samples"
```

---

### Task 4: Implement the three deterministic long-or-cash baselines

**Files:**

- Create: `src/backtest/e0/runners.py`
- Create: `tests/test_backtest/e0/test_runners.py`

**Interfaces:**

- Produces protocol `E0Runner` with `runner_id: RunnerId`, `version: str`, and `async run(sample: E0Sample, evidence: FrozenEvidence, context: RunnerContext) -> RunnerDecision`.
- Produces `CashRunner`, `BuyHoldRunner`, and `Momentum20Runner`.
- `RunnerDecision` is an internal frozen action/confidence/reason model converted by the engine into `DecisionRecord`.

- [ ] **Step 1: Write baseline RED tests**

```python
@pytest.mark.asyncio
async def test_cash_runner_never_trades() -> None:
    result = await CashRunner(version="cash:v1").run(SAMPLE, EVIDENCE, CONTEXT)
    assert result.action is DecisionAction.CASH
    assert result.position_fraction == Decimal("0")


@pytest.mark.parametrize(("return_20d", "expected"), [("0.01", "LONG"), ("0", "CASH"), ("-0.01", "CASH")])
@pytest.mark.asyncio
async def test_momentum_rule_is_positive_return_only(return_20d: str, expected: str) -> None:
    evidence = _evidence_with_20d_return(Decimal(return_20d))
    result = await Momentum20Runner(version="momentum20:v1").run(SAMPLE, evidence, CONTEXT)
    assert result.action.value == expected
```

Also prove B1 and B3 use the manifest position fraction, reject fewer than 20 completed historical bars, and cannot read label bars.

- [ ] **Step 2: Run baseline tests and verify RED**

Run: `python -m pytest tests/test_backtest/e0/test_runners.py -k "cash or buy_hold or momentum" -q`

- [ ] **Step 3: Implement B0/B1/B3**

B0 returns `CASH`; B1 returns `LONG` only when the decision-time execution proof says entry is tradable; B3 returns `LONG` only when `(latest_close / close_20_sessions_ago) - 1 > 0`. No runner reads `HorizonLabel` or any post-decision bar.

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_backtest/e0/test_runners.py -k "cash or buy_hold or momentum" -q
git add -- src/backtest/e0/runners.py tests/test_backtest/e0/test_runners.py
git commit -m "feat: add E0 deterministic baselines"
```

---

### Task 5: Adapt frozen evidence to A0 and A1 without changing production behavior

**Files:**

- Modify: `src/backtest/e0/runners.py`
- Modify: `tests/test_backtest/e0/test_runners.py`

**Interfaces:**

- Produces `FrozenDataCollector(DataCollector)` whose overridden reads return only the frozen sample payload and raise `FrozenEvidenceError` for another symbol, unlisted capability, or any request beyond `as_of`.
- Produces `LitchiRunner(orchestrator_factory: Callable[[DataCollector], DebateOrchestrator])` for A0.
- Produces `SingleAgentDeepSeekRunner(invoke: StructuredInvoker)` for A1.
- Produces frozen `SingleAgentDecision(action: LONG | CASH | ABSTAIN, confidence: float, rationale: str)`.

- [ ] **Step 1: Write frozen collector anti-leakage RED tests**

Prove `get_klines()` exposes only completed bars with timestamps before `decision_at`; current quote/news/financial/industry/sentiment calls return the frozen payload; another stock, live provider access, or a post-`as_of` bar raises `FrozenEvidenceError` before any LLM call.

- [ ] **Step 2: Write A0 contract RED tests**

Inject a fake orchestrator factory and assert:

- it receives only `FrozenDataCollector`;
- `news_evidence_service=None` and `quote_evidence_service=None` are explicit because the collector payload is already frozen and hash-verified;
- `enable_risk`, `enable_trader`, `enable_reflection`, `enable_trust`, and `enable_mirror` match the frozen A0 configuration in the manifest;
- `Bullish` maps to `LONG`; `Bearish`/`Neutral` maps to `CASH`; evidence rejection maps to `ABSTAIN`; malformed production output raises `RunnerContractError`.

- [ ] **Step 3: Implement A0 adapter without editing `src/debate/` or production Prompts**

The adapter calls `DebateOrchestrator(...).run(DebateInput(...))` with a deterministic `session_id = f"{experiment_id}:{sample_id}:A0:{repetition}"`. It stores the raw `DebateResult` hash and maps `vote_summary.consensus`, `vote_summary.confidence`, and any enabled deterministic risk rejection into `RunnerDecision`.

- [ ] **Step 4: Write A1 contract RED tests**

Assert one structured DeepSeek call receives the same frozen market brief and exact question as A0, the manifest model ID, system Prompt version `e0-single-agent:v1`, and no A0 analyses. Assert the output schema is `SingleAgentDecision`, and malformed/unsupported action is a contract failure rather than a silent `CASH` fallback.

- [ ] **Step 5: Implement the frozen A1 Prompt**

Use this versioned system Prompt verbatim and hash it into the manifest:

```text
你是 E0 闭卷评测中的单一投资分析 Agent。你只能使用用户提供的冻结时点证据，不能请求当前数据、猜测缺失事实或参考其他参赛器。目标周期固定为未来 5 个交易日，只允许 LONG、CASH、ABSTAIN：证据完整且判断为正收益倾向时选 LONG；不持有或卖出已有仓位时选 CASH；证据不足、冲突或无法可靠判断时选 ABSTAIN。confidence 表示你对本次方向判断的原始主观把握，范围 0 到 1，不得声称已经校准。输出必须严格符合 SingleAgentDecision。
```

Call only `src.utils.llm.llm_service.invoke_structured`; do not instantiate a model client directly.

- [ ] **Step 6: Run A0/A1 tests and commit**

```powershell
python -m pytest tests/test_backtest/e0/test_runners.py -q
ruff check src/backtest/e0/runners.py tests/test_backtest/e0/test_runners.py
pyright src/backtest/e0/runners.py
git add -- src/backtest/e0/runners.py tests/test_backtest/e0/test_runners.py
git commit -m "feat: adapt frozen evidence to E0 AI runners"
```

---

### Task 6: Generate point-in-time labels and explicit A-share costs

**Files:**

- Create: `src/backtest/e0/labeling.py`
- Create: `tests/test_backtest/e0/test_labeling.py`

**Interfaces:**

- Produces `calculate_fees(side: Literal["buy", "sell"], notional: Decimal, profile: FeeProfile) -> Decimal`.
- Produces `label_sample(sample: E0Sample, future_bars: AdjustedKlineSeries, *, fee_profile: FeeProfile, position_profile: PositionProfile) -> LabelRecord`.
- Produces stable non-tradability codes `entry_suspended`, `entry_limit_locked`, `exit_suspended`, `exit_limit_locked`, and `horizon_not_covered`.

- [ ] **Step 1: Write fee RED tests**

Verify buy commission minimum, sell commission minimum, sell-only stamp tax, transfer fee on both sides, symmetric configured slippage, and zero-notional cash/abstain. Use exact `Decimal` assertions; no binary-float comparison.

- [ ] **Step 2: Run fee tests and verify RED**

Run: `python -m pytest tests/test_backtest/e0/test_labeling.py -k fee -q`

- [ ] **Step 3: Implement explicit fee arithmetic**

Use `max(notional * commission_rate, minimum_commission)` only for non-zero executed notional, quantize money to `Decimal("0.01")` with `ROUND_HALF_EVEN`, and include profile/version in every label.

- [ ] **Step 4: Write point-in-time label RED tests**

Cover exact trading-session offsets 1/5/20, no calendar-day counting, QFQ lineage matching the sample RAW snapshot, post-decision factor leakage rejection, entry/exit suspension, locked limit, missing horizon, and identical label for every runner on the same sample before action/cost application.

- [ ] **Step 5: Implement label blindness and execution outcome**

The labeler receives future bars only after all runner decisions are terminal. It returns market returns plus per-action net returns under the one shared position/fee profile. It does not import `src.debate`, `src.agents`, or `src.utils.llm`.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m pytest tests/test_backtest/e0/test_labeling.py -q
git add -- src/backtest/e0/labeling.py tests/test_backtest/e0/test_labeling.py
git commit -m "feat: label E0 outcomes with explicit costs"
```

---

### Task 7: Reuse trust calibration arithmetic and compute full-denominator reports

**Files:**

- Modify: `src/debate/trust.py`
- Modify: `tests/test_debate/test_trust.py`
- Create: `src/backtest/e0/metrics.py`
- Create: `src/backtest/e0/reporting.py`
- Create: `tests/test_backtest/e0/test_metrics.py`

**Interfaces:**

- Produces public pure helpers `calculate_brier(confidences: Sequence[float], correctness: Sequence[bool]) -> float` and `build_calibration_curve(...)` in `src.debate.trust`.
- Existing `TrustTracker._compute_metrics()` delegates to these helpers with unchanged outputs.
- Produces `build_e0_report(manifest, decisions, labels, stability) -> E0Report` and `render_report_markdown(report: E0Report) -> str`.

- [ ] **Step 1: Write trust-helper equivalence RED tests**

Construct the existing `AgentOutcome` fixture set, assert the new helper Brier equals current `TrustTracker._compute_metrics(...).brier_score`, and assert the public calibration curve exactly equals the existing private arithmetic.

- [ ] **Step 2: Extract pure helpers without changing behavior**

Keep bucket boundaries and the current minimum-sample behavior unchanged. Run `python -m pytest tests/test_debate/test_trust.py -q` before E0 metric work.

- [ ] **Step 3: Write E0 full-denominator metric RED tests**

Cover direction accuracy, balanced accuracy, Brier, ECE from manifest bucket edges, high-confidence error rate, net/relative return, paired A0−A1 five-day return, hit rate, profit factor, turnover, max drawdown, tail loss, worst single/consecutive loss, abstain/failure/timeout rates, freshness, latency, Token, model cost, and four-regime plus 1/5/20-day strata.

Include a failed A0 and an abstaining A1 fixture and assert both remain in runner counts and paired denominator disclosure; economic pairs without two executable returns are reported as unavailable pairs, not deleted records.

- [ ] **Step 4: Implement metrics using existing helpers**

Reuse `calculate_max_drawdown`, `calculate_sharpe`, and `calculate_profit_factor` from `src.backtest.metrics` where their inputs match; do not copy their formulas. Reuse the public Brier/calibration helpers from `src.debate.trust`. Implement ECE only in E0 as `sum(bucket_count / total * abs(bucket_accuracy - bucket_mean_confidence))`.

- [ ] **Step 5: Write and implement stability audit aggregation**

For the frozen 20-sample subset and repetitions 1–3, report per-runner direction agreement, position range, confidence range/standard deviation, failures, and timeouts. Never average away missing repetitions.

- [ ] **Step 6: Implement deterministic JSON/Markdown rendering**

`report.md` must show manifest/version block, complete denominators, A0/A1 paired primary table, B0/B1/B3 context, safety, runtime, stability, all four regimes, limitations, and adjudication. Rendering is pure and does not call an LLM.

- [ ] **Step 7: Run tests and commit**

```powershell
python -m pytest tests/test_debate/test_trust.py tests/test_backtest/e0/test_metrics.py -q
git add -- src/debate/trust.py tests/test_debate/test_trust.py src/backtest/e0/metrics.py src/backtest/e0/reporting.py tests/test_backtest/e0/test_metrics.py
git commit -m "feat: compute complete E0 comparison reports"
```

---

### Task 8: Encode the four-way E0 adjudication truth table

**Files:**

- Create: `src/backtest/e0/adjudication.py`
- Create: `tests/test_backtest/e0/test_adjudication.py`

**Interfaces:**

- Produces `adjudicate(report: E0Report, integrity: E0IntegrityReport) -> E0Adjudication`.

- [ ] **Step 1: Write the exact truth-table RED tests**

Test `INVALID` first for future leakage, manifest/version mismatch, removed records, hard-gate bypass, label visibility, or terminal overwrite. Test `STOP_AND_ABLATE` when A1 is no worse than A0 on five-day net return, Brier, high-confidence error, and max drawdown; at least two quality/risk metrics are strictly better; and A0 cost or latency is not lower. Test `EXPAND_SAMPLE` when A0 paired net return is higher, at least one of Brier/ECE/high-confidence error improves, and max drawdown/tail loss/hard-gate bypass do not worsen. Every other valid combination is `INSUFFICIENT_EVIDENCE`.

- [ ] **Step 2: Run adjudication tests and verify RED**

Run: `python -m pytest tests/test_backtest/e0/test_adjudication.py -q`

- [ ] **Step 3: Implement pure ordered adjudication**

Evaluate `INVALID`, then dominance/stop, then expansion, then insufficient evidence. Store the exact boolean predicates and compared values in `E0Adjudication.reasons`; do not return only prose.

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_backtest/e0/test_adjudication.py -q
git add -- src/backtest/e0/adjudication.py tests/test_backtest/e0/test_adjudication.py
git commit -m "feat: encode E0 adjudication rules"
```

---

### Task 9: Orchestrate resume-safe runs and expose the manual CLI

**Files:**

- Create: `src/backtest/e0/engine.py`
- Create: `scripts/run_e0.py`
- Create: `tests/test_backtest/e0/test_engine.py`
- Create: `tests/test_scripts/test_run_e0.py`

**Interfaces:**

- Produces `E0Engine(store, runners, labeler, clock, timeout_seconds)`.
- Produces `async run_decisions()`, `publish_labels()`, `publish_report()`, and `verify()`.
- CLI modes: `freeze`, `dry-run`, `run`, `label`, `report`, `verify`.

- [ ] **Step 1: Write engine status-mapping RED tests**

Assert a normal decision becomes `COMPLETE`, explicit runner abstention becomes `ABSTAIN`, expected runner exception becomes `FAILED`, `asyncio.TimeoutError` becomes `TIMEOUT`, and programmer-contract errors abort the experiment. Each record includes measured latency and captured Token/cost delta; one runner failure never invokes another runner.

- [ ] **Step 2: Implement decision orchestration and idempotent resume**

Iterate manifest samples then runner IDs in stable order. Skip only keys already present with a valid hash. For the frozen stability subset, schedule repetitions 2 and 3 after the primary pass; all other records use repetition 1. Persist each terminal record before advancing.

- [ ] **Step 3: Write label/report phase-separation RED tests**

Assert `publish_labels()` refuses until every required decision record exists, and `publish_report()` refuses until every label exists and store verification is clean. Assert report regeneration is byte-identical and cannot call any runner or LLM.

- [ ] **Step 4: Implement phase separation**

The engine receives future bars only through the label phase. The decision phase object has no labeler or future-bar handle. `publish_report()` loads only frozen JSON/JSONL artifacts and calls metrics/adjudication/reporting.

- [ ] **Step 5: Write five-sample deterministic dry-run RED test**

Use `fixture_mode=True`, fake A0/A1, and synthetic frozen evidence. Assert the directory contains exactly `manifest.json`, `manifest.sha256`, `decisions.jsonl`, `labels.jsonl`, `report.json`, `report.md`, and `terminal.json`; all five runners appear for all five samples and no network/LLM call occurs.

- [ ] **Step 6: Implement CLI parsing with no real-run defaults**

`freeze` requires explicit manifest input and output root. `run` requires an existing verified manifest plus API credentials already managed by project settings. `dry-run` is deterministic and refuses a non-fixture manifest. `label`, `report`, and `verify` never initialize LLM services. Print concise stable diagnostics and exit non-zero on integrity/configuration failure.

- [ ] **Step 7: Run focused E0 suite and commit**

```powershell
python -m pytest tests/test_backtest/e0 tests/test_scripts/test_run_e0.py -q
ruff check src/backtest/e0 scripts/run_e0.py tests/test_backtest/e0 tests/test_scripts/test_run_e0.py
pyright src/backtest/e0 scripts/run_e0.py
git add -- src/backtest/e0/engine.py scripts/run_e0.py tests/test_backtest/e0/test_engine.py tests/test_scripts/test_run_e0.py
git commit -m "feat: orchestrate resumable E0 benchmarks"
```

---

### Task 10: Publish the package boundary and synchronize project truth

**Files:**

- Create: `src/backtest/e0/__init__.py`
- Modify: `src/backtest/__init__.py`
- Modify all documentation files listed in File Structure.

**Interfaces:**

- Public top-level exports are `E0Engine`, `E0Manifest`, `E0Report`, `E0Verdict`, `FeeProfile`, `PositionProfile`, `RegimePolicy`, and `freeze_samples`.
- Internal collectors, Prompt text, store helpers, and hashing helpers remain under `src.backtest.e0` and are not promoted to `src.backtest`.

- [ ] **Step 1: Write the public export RED test**

Add to `tests/test_backtest/e0/test_models.py`:

```python
def test_backtest_package_exports_only_stable_e0_boundary() -> None:
    from src import backtest
    assert backtest.E0Engine is E0Engine
    assert backtest.E0Manifest is E0Manifest
    assert not hasattr(backtest, "FrozenDataCollector")
```

- [ ] **Step 2: Implement exports and run all E0 tests**

Run: `python -m pytest tests/test_backtest/e0 tests/test_scripts/test_run_e0.py tests/test_debate/test_trust.py -q`

- [ ] **Step 3: Synchronize documentation without claiming a real result**

Record: E0 implementation exists; deterministic dry-run is green; real E0-100 has not run; `RegimePolicy v1`, `FeeProfile v1`, position, confidence bucket, and expansion count still require explicit user approval; KR-4 remains paused. Keep TD-074 open and register any discovered implementation debt using the project template.

- [ ] **Step 4: Create learning card 51**

Explain why manifest freezing differs from caching, how label blindness is enforced structurally, why failed/abstained/timeouts stay in the denominator, and why paired A0−A1 comparisons are primary. Include a 3–5 minute `dry-run`/tamper/`verify` exercise and links to cards 49–50.

- [ ] **Step 5: Run five-sync reference cleanup**

```powershell
rg -n "E0-100|validation-first|KR-4.*暂停|DecisionSnapshot|run_e0|FeeProfile|RegimePolicy" README.md docs src tests scripts
```

Review every current-status match, preserve historical logs as history, and ensure there is one E0 design, one implementation plan, one error/adjudication table, and one CLI.

- [ ] **Step 6: Commit Task 10**

Stage only the explicit in-scope paths and commit:

```powershell
git add -- src/backtest/e0/__init__.py src/backtest/__init__.py README.md docs/00-overview/ROADMAP.md docs/01-guides/HANDOVER.md docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md docs/03-modules/07-backtesting/README.md docs/03-modules/07-backtesting/SPEC.md docs/04-changelog/logs/2026-08-10/2026-08-10.md docs/05-decisions/ADR-013-multi-source-evidence.md docs/06-departments/00-cross-cutting/HANDOVER.md docs/06-departments/07-backtesting/HANDOVER.md docs/06-departments/07-backtesting/DEBT.md docs/learning/51-closed-book-decision-evaluation.md docs/learning/README.md tests/test_backtest/e0/test_models.py
git commit -m "docs: hand off E0 benchmark implementation"
```

---

### Task 11: Independent review, anti-cheat audit, and full release gate

**Files:**

- Review all files changed by Tasks 1–10.
- Modify only files needed to resolve findings.

**Interfaces:**

- Produces an implementation ready for explicit user parameter approval and manual E0-100 execution.
- Does not execute the real 100-sample LLM experiment.

- [ ] **Step 1: Request independent architecture/security review**

Review for future-data leakage, manifest mutability, label visibility, denominator deletion, model fallback, hidden policy defaults, incorrect A0/A1 isolation, fee asymmetry, resume corruption, Prompt/version drift, and accidental production behavior changes.

- [ ] **Step 2: Apply valid findings using RED→GREEN tests**

For every accepted finding, add the smallest failing test, prove RED, apply the minimal fix, rerun the owning E0 test file, and append the finding/resolution to the 2026-08-10 work log. Programmer-contract errors remain experiment failures; expected per-sample runner failures remain records.

- [ ] **Step 3: Run the deterministic dry-run and tamper audit**

```powershell
python scripts/run_e0.py dry-run --root .tmp/e0-dry-run --experiment-id e0-dry-run
python scripts/run_e0.py verify --root .tmp/e0-dry-run/e0-dry-run
python -m pytest tests/test_backtest/e0 tests/test_scripts/test_run_e0.py -q
```

Use a task-scoped temporary directory and remove only that verified directory after evidence is recorded.

- [ ] **Step 4: Run static and full project gates**

```powershell
ruff check src/backtest/e0 src/debate/trust.py scripts/run_e0.py tests/test_backtest/e0 tests/test_scripts/test_run_e0.py tests/test_debate/test_trust.py
pyright src/backtest/e0 src/debate/trust.py scripts/run_e0.py
python scripts/check.py --full
```

- [ ] **Step 5: Verify the strategic stop**

Confirm no real benchmark artifact was committed, no new source/API/frontend/Agent/dependency exists, KR-4 remains paused, TD-074 remains open, and current docs say “implementation ready; real E0-100 not run.” Confirm the worktree is clean after final commits.

- [ ] **Step 6: Stop for user parameter approval**

Present the proposed explicit `RegimePolicy v1`, `FeeProfile v1`, `PositionProfile v1`, `ConfidencePolicy v1`, and expansion count for user approval. Do not run real LLM samples, push, merge, or start KR-4 in the same step.
