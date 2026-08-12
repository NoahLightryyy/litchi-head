# Session Snapshot Scope Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the uncommitted over-engineered native directory backend, retain the last reviewed recovery implementation, and document/test the trusted-local-user threat boundary.

**Architecture:** Session snapshots remain disposable cache files beneath a user-owned session root; Git/worktree and repository evidence remain authoritative. Existing directory components are rejected when they are symlinks or Windows reparse points, but the implementation does not attempt to defeat a same-account process that mutates a directory after validation. Any uncertainty fails closed and routes recovery back to read-only Git evidence.

**Tech Stack:** Python 3.12, pathlib/os, Pydantic, pytest, Ruff, Pyright, Git, Markdown.

## Global Constraints

- Do not implement NT handle-relative directory I/O or a new filesystem abstraction.
- Do not defend against a same-account malicious process changing a directory after validation.
- Do not weaken project/worktree/branch/HEAD/dirty/evidence validation, legacy quarantine, exact seven-day freshness, CLI exit codes, secret redaction, atomic no-clobber publication, or bounded same-handle file reads.
- A pre-existing symlink or Windows reparse point in `v2/<project-key>/<worktree-key>` must fail closed.
- A storage or inspection failure must never expose or execute `exact_next_step`; recovery returns to read-only Git/SDD/HANDOVER/work-log evidence.
- Preserve unrelated user changes. Do not push.

---

### Task 1: Remove the Uncommitted Native Backend

**Files:**
- Restore: `scripts/session_state_git.py`
- Restore: `scripts/session_state_store.py`
- Restore: `tests/test_scripts/test_session_state_git.py`
- Restore: `tests/test_scripts/test_session_state_store.py`
- Update ignored evidence: `.superpowers/sdd/2026-08-12-session-snapshot-scope-correction/task-1-report.md`

**Interfaces:**
- Consumes: committed state at `de7350a` plus design commit `69146ba`.
- Produces: a clean tracked worktree whose recovery code equals the reviewed state before Round 5.

- [ ] **Step 1: Capture the exact discard scope**

Run:

```powershell
git status --short
git diff --name-only
git diff --numstat
```

Expected: exactly the four Python files listed above are modified; the design and plan are committed.

- [ ] **Step 2: Restore only the four abandoned files**

Run:

```powershell
git restore --source=HEAD -- scripts/session_state_git.py scripts/session_state_store.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py
```

Expected: the approximately 983-line Round 5 diff disappears without touching committed Task 1–5 work or ignored reports.

- [ ] **Step 3: Verify the recovered baseline**

Run:

```powershell
git status --short
python -m pytest tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py -q
ruff check scripts/session_state_models.py scripts/session_state_git.py scripts/session_state_store.py scripts/session_state.py tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py
pyright scripts/session_state_models.py scripts/session_state_git.py scripts/session_state_store.py scripts/session_state.py tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py
```

Expected: tracked worktree clean; the committed Tasks 1–5 suite passes with only the existing Windows symlink-capability skip; Ruff and Pyright pass.

- [ ] **Step 4: Record evidence**

Write the exact discarded file list, line counts, commands, exit codes, and test totals to the ignored report. Do not force-add it. No source commit is required because this task removes only uncommitted changes.

---

### Task 2: Encode the Simplified Product Boundary

**Files:**
- Modify: `scripts/session_state_store.py`
- Modify: `tests/test_scripts/test_session_state_store.py`
- Update ignored evidence: `.superpowers/sdd/2026-08-12-session-snapshot-scope-correction/task-2-report.md`

**Interfaces:**
- Consumes: `snapshot_directory(root: Path, snapshot: SessionSnapshot) -> Path`, `write_snapshot(...)`, and `discover_v2(...)` from the recovered baseline.
- Produces: a small pre-existing-component guard shared by save and discovery, with no TOCTOU security claim.

- [ ] **Step 1: Write product-boundary tests first**

Add deterministic tests that:

```python
def test_write_rejects_preexisting_v2_reparse_component(...): ...
def test_discovery_rejects_preexisting_worktree_reparse_component(...): ...
def test_snapshot_serialization_unicode_error_is_sanitized(...): ...
```

On Windows, create a real directory junction with `cmd /c mklink /J` when available; on POSIX, use a directory symlink. The tests must create the redirection before calling production code. They must not mutate a normal directory after validation and must not assert resistance to a same-account concurrent attacker. The Unicode test recursively checks `str`, `args`, `__cause__`, and `__context__` for absence of the payload marker.

- [ ] **Step 2: Run the new tests and witness RED**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state_store.py -q -k "preexisting or serialization_unicode"
```

Expected: at least one test fails against the recovered baseline for the missing component guard or serialization boundary.

- [ ] **Step 3: Implement the minimum guard**

Add one focused helper that inspects only already-existing components below the resolved session root. Use `os.lstat`/`Path.is_symlink` on POSIX and the existing Windows reparse attribute query where already available. Reject detected redirections with the stable store operational exception. Keep ordinary pathlib-based creation, enumeration, publication, and reading; do not introduce directory handle pinning or native relative I/O.

Wrap JSON serialization and UTF-8 encoding so `UnicodeError` becomes the existing stable sanitized store exception after leaving the active `except` context.

- [ ] **Step 4: Run focused and cumulative tests**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state_store.py -q
python -m pytest tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py -q
ruff check scripts/session_state_store.py tests/test_scripts/test_session_state_store.py
pyright scripts/session_state_store.py tests/test_scripts/test_session_state_store.py
git diff --check
```

Expected: all focused/cumulative tests pass; no new skip hides the real pre-existing junction scenario; Ruff, Pyright, and diff check pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts/session_state_store.py tests/test_scripts/test_session_state_store.py
git commit -m "fix: enforce practical snapshot scope boundary"
```

Record RED/GREEN commands and exact results in the ignored report; never force-add it.

---

### Task 3: Synchronize Threat Model, Debt, Learning, and Work Log

**Files:**
- Modify: `docs/superpowers/specs/2026-08-11-session-recovery-reliability-design.md`
- Modify: `docs/01-guides/debt/ROUTER.md` and the routed debt file selected by that router
- Create or modify: `docs/learning/` card selected from `docs/learning/README.md` numbering
- Create or modify: `docs/04-changelog/logs/2026-08-12/` latest AI work log
- Modify: `docs/01-guides/HANDOVER.md` only if it currently claims a stronger filesystem threat model
- Update ignored evidence: `.superpowers/sdd/2026-08-12-session-snapshot-scope-correction/task-3-report.md`

**Interfaces:**
- Consumes: the approved simplification design and Task 2 implementation/test evidence.
- Produces: one consistent project statement that snapshots are disposable cache under a trusted-local-user threat model.

- [ ] **Step 1: Locate all stronger claims and debt routes**

Run:

```powershell
rg -n "handle-relative|NtCreateFile|junction|reparse|符号链接|链接目标变化|安全存储|session snapshot|会话快照" AGENTS.md README.md docs scripts tests
Get-Content -Raw docs/01-guides/debt/ROUTER.md
Get-Content -Raw docs/01-guides/debt/TEMPLATE.md
Get-Content -Raw docs/learning/README.md
```

Expected: a finite list of claims and the correct debt/log/card destinations.

- [ ] **Step 2: Update the canonical design and project records**

State explicitly:

- snapshots are disposable cache and Git/worktree is authoritative;
- pre-existing redirections fail closed;
- same-account post-validation directory mutation is outside the current threat model;
- any storage uncertainty returns to read-only repository recovery;
- the abandoned native backend was not committed or shipped.

Register a deferred security debt only for the condition that would reopen the decision: snapshots cross a trust boundary, contain sensitive material, or run in a privileged/shared service. Record the real junction escape evidence and corrective rollback in the 2026-08-12 work log. Add a concise learning card explaining threat-model budgeting and TOCTOU boundaries with links to the real project files.

- [ ] **Step 3: Clean stale references**

Run the search from Step 1 again. Expected: no document claims that this implementation defeats post-validation same-account junction mutation or uses NT handle-relative storage.

- [ ] **Step 4: Verify and commit documentation**

Run:

```powershell
python scripts/check.py --full
git diff --check
git status --short
```

Expected: all five project gates pass. Then stage only Task 3 documents and commit:

```powershell
git commit -m "docs: record snapshot recovery threat boundary"
```

---

### Task 4: Final Independent Verification and Task 5 Closeout

**Files:**
- Modify: `.superpowers/sdd/2026-08-11-session-recovery-reliability/progress.md` (ignored ledger)
- Modify: `.superpowers/sdd/2026-08-12-session-snapshot-scope-correction/progress.md` (ignored ledger)
- Modify tracked files only if the final independent review finds a load-bearing defect and a reviewed fix is approved.

**Interfaces:**
- Consumes: commits from Tasks 2–3 and all Tasks 1–5 session recovery code.
- Produces: clean independent review evidence and an unblocked handoff to the original plan's Task 6.

- [ ] **Step 1: Run fresh gates**

```powershell
python -m pytest tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py -q
python scripts/check.py --full
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"
git diff --check
git status --short
```

Expected: focused suite and full gate pass; real incident remains exit `2` with `LEGACY_UNVERIFIABLE` and no TD-072 next step; tracked worktree clean.

- [ ] **Step 2: Independent Python/security-boundary review**

Review the entire correction range against the approved simplification design. The reviewer must distinguish actual product requirements from the explicitly excluded same-account post-validation mutation scenario. Critical/Important findings inside the approved boundary block completion; excluded-threat observations are documented, not silently converted back into implementation scope.

- [ ] **Step 3: Close ledgers**

Record exact commits, tests, the discarded Round 5 scope, review verdict, and the threat-model ruling in both ignored ledgers. Mark the correction plan complete and replace the original Task 5 blocked line with a completed line that points to this corrective plan. Do not force-add either ledger.

