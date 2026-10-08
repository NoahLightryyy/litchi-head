# README Public Status Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the stale root README and make future public-status synchronization part of the existing closeout path, with one narrow automated guard instead of another organization layer.

**Architecture:** Treat the root `README.md` as a public projection of a small set of canonical global-status documents. Keep detailed truth in ROADMAP/HANDOVER/requirements, update the projection when those sources change, and let `scripts/check.py` fail only when an ahead-or-uncommitted change touches one of those sources without touching the root README. Do not create a documentation service, new department, migration, or generalized document dependency graph.

**Tech Stack:** Python 3.13, pytest, Ruff, Pyright, Markdown, Git name-only diff discovery.

## Global Constraints

- Do not add a new department, Agent, service, state store, dependency, hook framework, or documentation platform.
- Do not move files or reorganize directories.
- Preserve all existing business and runtime behavior; this change is documentation/process infrastructure only.
- The automated guard must be narrow and deterministic. It must not require README edits for ordinary module docs, learning cards, logs, or debt records.
- The guard must see both uncommitted files and commits ahead of the configured upstream, so committing before the final gate cannot hide a missed README update.
- Repositories without an upstream must fall back to uncommitted-file checking and must not fail merely because no upstream exists.
- `--diff REF` remains authoritative when explicitly supplied; upstream-ahead discovery is only added for the default `HEAD` mode.
- Remove the impression that architecture completeness proves investment performance. State explicitly that E0-100 is approved but not implemented or passed.
- Present named investor personas as the current interface/implementation, not as a validated moat.
- Do not publish exact E0 fee, regime, or position parameters; those still require separate user approval.
- Reuse learning card 21 instead of creating another card.
- No new debt item: the known process gap is fixed in this batch. Record that decision in the work log.
- Finish with focused tests plus `python scripts/check.py --full` because `scripts/check.py` is shared quality infrastructure.

---

## File Structure

**Modify:**

- `README.md` — correct product positioning, current KR/E0 status, architecture caveat, organization wording, and test evidence presentation.
- `docs/03-modules/01-data-collection/README.md` — replace the obsolete “validation checkpoint planning” next step with the approved E0 design / implementation-plan boundary.
- `tests/test_scripts/test_check.py` — TDD coverage for public-status triggers, upstream-ahead discovery, no-upstream fallback, and main-gate behavior.
- `scripts/check.py` — add the narrow README public-status synchronization gate.
- `docs/01-guides/workflow/CLOSING.md` — put public-surface synchronization in the strong gate and full closeout checklist.
- `docs/01-guides/workflow/DEVELOPMENT.md` — replace the overly broad “every code change” README rule with exact semantic triggers and list the automated canonical sources.
- `docs/learning/21-engineering-discipline.md` — extend the existing discipline card with the distinction between canonical truth and a public projection.
- `docs/04-changelog/logs/2026-08-10/2026-08-10.md` — record the process failure, correction, exact files, and verification.
- `docs/04-changelog/logs/README.md` — extend the existing 2026-08-10 summary; do not add a duplicate date row.

**Create:**

- None.

---

### Task 1: Correct the public README without overstating validation

**Files:**

- Modify: `README.md`
- Modify: `docs/03-modules/01-data-collection/README.md`

- [ ] **Step 1: Replace fragile and misleading top-level claims**

In `README.md`:

- Change the subtitle from “个人多智能体投资决策助手 — 你的 AI 投研团队” to “个人投资研究与决策证据助手 — 多智能体是待验证的实现手段”.
- Replace the exact-count badge with a non-drifting CI claim such as `tests-pytest%20passing`; keep the GitHub Actions status badge as the live source.
- Replace the goal sentence with wording that promises structured evidence, disagreement, risk, and valuation support while leaving the final investment decision to the user.
- Add an `IMPORTANT` callout immediately after the goal:

```markdown
> [!IMPORTANT]
> **当前证据成熟度**：工程链路和失败关闭已有测试证据，但项目尚未证明多智能体比
> 单 Agent、简单规则或买入持有更能创造成本后收益。E0-100 离线闭卷评测设计已批准，
> 尚未实施、尚无胜负结论；KR-4～KR-6 在 E0 裁决前暂停。
```

- [ ] **Step 2: Mark architecture and personas as hypotheses under test**

Before the architecture diagram, add:

```markdown
> 下图是当前实现，不是已经验证的最优组织。E0 将通过 Full/Single 对照和后续消融实验
> 检验辩论、人格、风控等层是否真的改善指标；删掉某层不降指标，就应合并或删除。
```

In the “7 位投资大师 + 灵感官” row, state that these are the current strategy/persona interface and that E0/ablation has not established an irreplaceable advantage. Do not claim simulation of the historical individuals.

- [ ] **Step 3: Synchronize actual KR-3 and E0 status**

Update the “多源证据完整性” row to say:

- KR-3B-2 is complete.
- `assemble_kline_business()` is the unified success/failure boundary.
- AI/API/frontend/risk/trading/backtest consumers have not switched yet.

Add or update a validation row to say:

- E0-100 design approved.
- It compares Full multi-agent, same-model Single DeepSeek, cash, buy-and-hold, and 20-day momentum.
- Implementation plan/data readiness/fee-regime-position parameters remain pending.
- There are no performance results yet.

Update Phase R text from “KR-3～6” and “baseline/影子验证 ⬜” to the truthful boundary: KR-3 complete, E0 design approved, KR-4～KR-6 paused until E0 decision.

Replace the evidence-maturity paragraph that currently says “先完成 K 线 KR-2～KR-6” with the approved E0-first sequence and link both:

- `docs/superpowers/specs/2026-08-10-e0-validation-checkpoint-design.md`
- `docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md`

- [ ] **Step 4: Make organization wording match the no-migration decision**

Change “工程架构（12 部门体系）” to “当前物理目录与责任映射”. Replace the paragraph below the tree with a note that:

- physical directories and responsibilities are preserved to avoid business loss;
- seven logical capability domains are a governance view, not a relocation;
- any later merge requires dependency inventory, acceptance checks, and rollback;
- the canonical decision is `docs/02-requirements/STRATEGY_VALIDATION_AND_ORG_EVOLUTION.md`.

Update the document-index description for `docs/06-departments/README.md` accordingly; do not advertise department count as a product advantage.

- [ ] **Step 5: Turn raw test counts into an auditable snapshot**

Replace both undated “1623 collected / 1600 passed” claims with one consistent historical statement:

```markdown
- **最近完整闸门快照（2026-08-10）** — 1718 collected；1695 passed、4 skipped、19 deselected；Ruff 与 Pyright 通过。最新状态以 CI 为准。
```

Do not describe this as proof of investment alpha.

- [ ] **Step 6: Correct the data-module handoff**

In `docs/03-modules/01-data-collection/README.md`, replace “下一步为 validation-first checkpoint 规划” with “E0-100 设计已批准，下一步仅编写实施计划并核验数据就绪；未获数值参数批准前不运行评测，也不进入 KR-4”. Keep the explicit list of disconnected downstream consumers.

- [ ] **Step 7: Search for the exact stale public claims**

Run:

```powershell
rg -n "1600 passed|1623 项测试|KR-3B-1 成功运行时|下一原子 KR-3B-2|先完成 K 线 KR-2～KR-6|baseline/影子验证 ⬜|工程架构（12 部门体系）" README.md docs/03-modules/01-data-collection/README.md
```

Expected: no matches.

- [ ] **Step 8: Commit the public correction**

```powershell
git add README.md docs/03-modules/01-data-collection/README.md
git commit -m "docs: correct public project status"
```

---

### Task 2: Add a narrow README synchronization gate with TDD

**Files:**

- Modify: `tests/test_scripts/test_check.py`
- Modify: `scripts/check.py`

- [ ] **Step 1: Write failing pure-function tests**

Add tests for this exact trigger set:

```python
PUBLIC_STATUS_FILES = {
    "docs/00-overview/ROADMAP.md",
    "docs/01-guides/HANDOVER.md",
    "docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md",
    "docs/02-requirements/STRATEGY_VALIDATION_AND_ORG_EVOLUTION.md",
}
```

Test these cases:

```python
def test_public_status_change_requires_root_readme_sync() -> None:
    assert check.missing_readme_sync(
        {"docs/00-overview/ROADMAP.md", "src/data/models.py"}
    ) == ("docs/00-overview/ROADMAP.md",)


def test_root_readme_satisfies_public_status_sync() -> None:
    assert check.missing_readme_sync(
        {"README.md", "docs/01-guides/HANDOVER.md"}
    ) == ()


def test_unrelated_docs_do_not_require_root_readme_sync() -> None:
    assert check.missing_readme_sync(
        {"docs/learning/21-engineering-discipline.md"}
    ) == ()
```

- [ ] **Step 2: Write failing upstream-ahead tests**

Add a unit test proving `git_upstream_diff()` parses a successful:

```text
git diff --name-only @{upstream}...HEAD
```

Add a second test proving return code 128 produces an empty set rather than failing the gate. Assert the exact subprocess argument list.

- [ ] **Step 3: Write a failing main-gate test**

Monkeypatch:

- `git_diff()` to return an unrelated uncommitted file;
- `git_upstream_diff()` to return `docs/00-overview/ROADMAP.md`;
- all executable `run_step()` calls to pass.

Assert `main()` returns `1`. Also update existing main/full tests to monkeypatch `git_upstream_diff()` to `set()` so they are hermetic.

- [ ] **Step 4: Run the red tests**

```powershell
python -m pytest tests/test_scripts/test_check.py -q
```

Expected: failures because `missing_readme_sync()` and `git_upstream_diff()` do not exist and the main gate is absent.

- [ ] **Step 5: Implement the pure trigger rule**

In `scripts/check.py`, add the constant and helper:

```python
PUBLIC_STATUS_FILES: frozenset[str] = frozenset(
    {
        "docs/00-overview/ROADMAP.md",
        "docs/01-guides/HANDOVER.md",
        "docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md",
        "docs/02-requirements/STRATEGY_VALIDATION_AND_ORG_EVOLUTION.md",
    }
)


def missing_readme_sync(changed_files: set[str]) -> tuple[str, ...]:
    """Return canonical public-status sources changed without root README."""
    if "README.md" in changed_files:
        return ()
    return tuple(sorted(changed_files & PUBLIC_STATUS_FILES))
```

Do not match directory prefixes and do not add a configurable dependency graph.

- [ ] **Step 6: Implement safe upstream-ahead discovery**

Add:

```python
def git_upstream_diff() -> set[str]:
    """Return committed files ahead of upstream, or empty when no upstream exists."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "@{upstream}...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}
```

Do not print or fail on the missing-upstream fallback.

- [ ] **Step 7: Wire the gate into both normal and full modes**

Always calculate `changed = git_diff(args.diff)`. Build public changes as:

```python
public_changed = set(changed)
if args.diff == "HEAD":
    public_changed.update(git_upstream_diff())
missing_public_sync = missing_readme_sync(public_changed)
```

Keep `--full` responsible only for test breadth and frontend breadth; it must not disable documentation consistency.

Add one in-process gate after Pyright and before tests:

```python
_s("\n  === README public status sync ===")
if missing_public_sync:
    _s("  [FAIL] canonical public status changed without README.md:")
    for path in missing_public_sync:
        _s(f"         {path}")
else:
    passes += 1
    _s("  [PASS] README public status sync")
```

Increase the base total from 3 to 4 and update the header/docstring order. Do not route this pure check through `run_step()`.

- [ ] **Step 8: Run focused green checks**

```powershell
python -m pytest tests/test_scripts/test_check.py -q
ruff check scripts/check.py tests/test_scripts/test_check.py
```

Expected: all pass.

- [ ] **Step 9: Commit the gate**

```powershell
git add scripts/check.py tests/test_scripts/test_check.py
git commit -m "ci: require public README status sync"
```

---

### Task 3: Put the rule in the existing closeout path

**Files:**

- Modify: `docs/01-guides/workflow/CLOSING.md`
- Modify: `docs/01-guides/workflow/DEVELOPMENT.md`
- Modify: `docs/learning/21-engineering-discipline.md`
- Modify: `docs/04-changelog/logs/2026-08-10/2026-08-10.md`
- Modify: `docs/04-changelog/logs/README.md`

- [ ] **Step 1: Strengthen the normal closeout gate**

In `CLOSING.md` §1 “发文更新”, add:

```text
✓ 公共表面同步：ROADMAP / 全局 HANDOVER / 两份全局战略基线有变更时，根 README 已同步
✓ python scripts/check.py 的 README public status sync 已通过
```

Add the same semantic check to the full closeout checklist. Do not add a separate approval committee or documentation phase.

- [ ] **Step 2: Correct the documentation audit trigger**

In `DEVELOPMENT.md`, replace the root README trigger “每次代码改动” with:

```text
用户可见能力、全局阶段/战略、KR 状态或公开验证证据变化时
```

Immediately below the table, document that `scripts/check.py` automatically enforces synchronization only for the four exact canonical files in `PUBLIC_STATUS_FILES`. State that module README, learning card, log, and debt-only changes do not trigger it.

This turns the previous blanket rule into a meaningful public-surface contract and avoids README churn.

- [ ] **Step 3: Update the existing engineering-discipline card**

Extend `docs/learning/21-engineering-discipline.md` with a short section:

- canonical documents hold detailed truth;
- root README is a public projection, not another truth source;
- upstream-ahead diff prevents “commit first, gate later” from hiding omissions;
- narrow exact-file triggers avoid a generalized dependency system;
- include a 3-minute exercise: change a temporary ROADMAP line, run the helper test/check, then revert the temporary edit before committing.

Update the card’s final date. Do not create card 52 and do not alter historical test counts elsewhere in the existing card unless directly necessary.

- [ ] **Step 4: Update the current work log and index**

Append a “README 公共状态同步缺口修复” section to `docs/04-changelog/logs/2026-08-10/2026-08-10.md` containing:

- user-reported symptom: repeated manual reminders;
- root cause: DEVELOPMENT rule existed, CLOSING/check gate omitted it;
- solution scope and why it does not create organizational overhead;
- exact changed files and final test evidence;
- no debt opened because the gap was closed in the same batch.

Extend the existing 2026-08-10 index summary in `docs/04-changelog/logs/README.md`; do not add another row.

- [ ] **Step 5: Perform reference cleanup**

Run:

```powershell
rg -n "每次代码改动|1600 passed|1623 项测试|下一原子 KR-3B-2|先完成 K 线 KR-2～KR-6|baseline/影子验证 ⬜" README.md docs/01-guides/workflow docs/03-modules/01-data-collection docs/04-changelog/logs/2026-08-10
```

Every remaining match must be either removed or explicitly historical. The work log may quote the old rule only if labeled as the corrected former rule.

- [ ] **Step 6: Commit process and learning synchronization**

```powershell
git add docs/01-guides/workflow/CLOSING.md docs/01-guides/workflow/DEVELOPMENT.md docs/learning/21-engineering-discipline.md docs/04-changelog/logs/2026-08-10/2026-08-10.md docs/04-changelog/logs/README.md
git commit -m "docs: enforce public status closeout"
```

---

### Task 4: Independent review and final verification

**Files:**

- Review all files modified in Tasks 1–3.
- Modify only files required to fix confirmed findings.

- [ ] **Step 1: Inspect the complete branch diff**

```powershell
git diff origin/codex/kr-3b-2-failure-diagnostics...HEAD -- README.md scripts/check.py tests/test_scripts/test_check.py docs/01-guides/workflow/CLOSING.md docs/01-guides/workflow/DEVELOPMENT.md docs/03-modules/01-data-collection/README.md docs/learning/21-engineering-discipline.md docs/04-changelog/logs/2026-08-10/2026-08-10.md docs/04-changelog/logs/README.md
```

Review specifically for:

- false README requirements from unrelated docs;
- missing detection of ahead commits;
- failure on repositories without upstream;
- `--full` accidentally skipping the sync gate;
- README claims that imply E0 has run or proved alpha;
- any new organization/process layer beyond the existing closeout and check script.

- [ ] **Step 2: Run focused verification**

```powershell
python -m pytest tests/test_scripts/test_check.py -q
ruff check scripts/check.py tests/test_scripts/test_check.py
pyright src/ backend/
git diff --check
```

- [ ] **Step 3: Run the shared-infrastructure full gate**

```powershell
python scripts/check.py --full
```

Expected:

- README public status sync passes from the branch’s ahead commits because `README.md` is included.
- Ruff passes.
- Pyright passes.
- Non-slow Python suite passes.
- Frontend type-check passes.

- [ ] **Step 4: Correct documentation evidence if counts changed**

If the final collected/passed/skipped/deselected counts differ from the Task 1 snapshot, update the dated snapshot in `README.md` and the work log to the observed values, then rerun `python scripts/check.py --full`. Do not convert the badge back to an exact count.

- [ ] **Step 5: Verify a clean worktree and ahead count**

```powershell
git status --short --branch
git log --oneline origin/codex/kr-3b-2-failure-diagnostics..HEAD
```

Do not push until the user explicitly requests it.

