# Litchi Head

**A multi-agent research platform for Chinese A-share markets, connecting market data, evidence validation and peer review in a traceable workflow.**

[中文](README.md) · [Architecture decisions](docs/05-decisions/README.md) · [Module documentation](docs/03-modules/README.md) · [CI](https://github.com/NoahLightryyy/litchi-head/actions)

Python · LangGraph · Pydantic · FastAPI · Next.js · TypeScript

## Overview

Litchi Head is a locally runnable, full-stack AI research system. Users can explore markets, sectors, stocks and ETFs, inspect prices and financial data, trace policy evidence, and obtain structured research through specialized agents, peer review and risk assessment.

The central engineering question is: **How can multi-agent analysis depend on inspectable evidence while remaining understandable when data is incomplete, services fail or tasks are interrupted?** The implementation connects data provenance, typed contracts, task state and model output within one workflow.

Delivered components include a LangGraph orchestration engine, cross-source data validation, recoverable research tasks, a web application and automated validation. The October 22, 2026 integration snapshot recorded **2,451 passing Python tests and 160 passing frontend tests**, with successful Python 3.12/3.13 and frontend [CI jobs](https://github.com/NoahLightryyy/litchi-head/actions/runs/39772044194). [Validation log](docs/04-changelog/logs/2026-10-22/2026-10-22-remaining-integration.md)

## User workflow

1. **Find a research subject:** explore markets and sectors, search stocks or ETFs, and inspect quotes, charts, financial indicators and source timestamps.
2. **Inspect the evidence:** review policy materials, citations and industry relationships. Source-backed maps and AI drafts labeled as unverified inference are presented separately.
3. **Run multi-perspective analysis:** once evidence gates pass, initiate analysts, strategy perspectives, peer review, independent assessment and aggregation.
4. **Review and follow up:** inspect structured findings and risk information, restore debate status when revisiting a page, and retain research and action records for reflection.

Stock, sector and ETF pages provide research entry points. `/policy` and `/capital` provide historical-policy and hypothetical-capital demonstrations. Capital previews use deterministic calculations and show whether account, fee and other required inputs are available.

## Engineering contributions

| Engineering question | Implementation | Entry point |
|---|---|---|
| How can multiple roles share a consistent structure? | LangGraph coordinates analysis, peer review, independent assessment and risk review; Pydantic validates data across module boundaries | [Orchestrator](src/debate/orchestrator.py) · [Models](src/debate/models.py) |
| What happens when evidence conflicts or expires? | Cross-source market/news checks retain provenance, timestamps and diagnostics; missing critical evidence blocks formal debate before model calls | [Evidence service](src/data/evidence_service.py) · [Gate](src/debate/evidence_gate.py) |
| How are intraday states separated from historical bars? | Separate completed daily bars from provisional intraday data, with components for RAW-data auditing, corporate actions and adjustment verification | [Price-data contracts](src/data/kline_business.py) · [Adjustments](src/data/kline_adjustment.py) |
| How can long-running research recover? | SQLite-backed policy research tasks link archived evidence and citations, enforce budget checks and preserve explicit failure states | [Research runtime](backend/policy_research.py) · [Runtime tests](tests/test_backend/test_policy_research_runtime.py) |
| How are monetary calculations kept out of language-model output? | Research generation is separate from Decimal-based single-buy calculations; typed contracts validate account, fee and permission context | [Capital preview](backend/capital_preview.py) · [Contract tests](tests/test_backend/test_policy_capital_contract.py) |
| How is the system delivered to users? | FastAPI and Next.js expose market data, charts, research status, failure diagnostics and task recovery, with CI across both stacks | [API](backend/main.py) · [Web app](frontend/) · [CI configuration](.github/workflows/ci.yml) |

## Architecture

```text
Market / news / financial data / policy materials
                       ↓
Adapters → provenance and freshness checks → typed evidence
                       ↓
Evidence gate → analysts → strategy perspectives → peer review
                       ↓
Independent assessment / aggregation → risk / planning → human review
                       ↓
Research records / reflection / trust statistics

FastAPI API ←→ Next.js web interface
```

Evidence validity, research generation and trade readiness are modeled separately, allowing the interface to expose errors and missing inputs. All model calls use a shared [LLM adapter](src/utils/llm.py). The current default is `deepseek-v4-pro` with thinking disabled, governed by `DEFAULT_MODEL`.

## Validation and research evaluation

**Engineering validation.** The October 22, 2026 integration snapshot recorded 2,451 passing Python tests, 7 skipped and 19 deselected; 160 frontend tests and the production build passed. CI includes Ruff, Pyright, Python 3.12/3.13 tests and coverage checks, plus frontend tests, type checking and builds. These snapshot-specific results are documented in the [validation log](docs/04-changelog/logs/2026-10-22/2026-10-22-remaining-integration.md) and [CI run](https://github.com/NoahLightryyy/litchi-head/actions/runs/39772044194).

**Research evaluation.** The repository implements [E0 offline sampling, execution and result storage](src/backtest/e0/) and preserves a [six-case research smoke test with raw records](docs/02-requirements/differentiation/SMOKE_RESULT_2026-10-18.md). The smoke test checks the research workflow; its small sample and unequal call budgets do not establish an advantage over a single-model baseline. Further comparisons follow the [baseline and shadow-validation plan](docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md).

**Scope.** The system supports research and human review. Its trading module provides plans and position calculations without live brokerage execution. Complete production provenance, continuous shadow evaluation and confidence calibration against real outcomes remain ongoing; test results do not establish investment returns. AI industry drafts are explicitly unverified inferences, not evidence of actual company relationships.

## Run locally

Requires Python 3.12+. Node.js 24 and pnpm 10.33.0 match the frontend CI environment. Live AI research requires DeepSeek credentials and access to upstream data services. A fresh deployment needs time to accumulate news coverage; unavailable critical sources produce explicit debate-blocking diagnostics. Automatic AI drafts may incur provider charges; successful results are cached.

```bash
git clone https://github.com/NoahLightryyy/litchi-head.git
cd litchi-head
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env      # PowerShell: Copy-Item .env.example .env

# Store credentials interactively in the OS credential manager.
python scripts/store-api-keys.py --set DEEPSEEK_API_KEY

corepack enable
corepack prepare pnpm@10.33.0 --activate
pnpm --dir frontend install --frozen-lockfile
```

Start two terminals from the repository root:

```bash
# Terminal 1, with the Python environment activated
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2
pnpm --dir frontend dev
```

Open the [web app](http://localhost:3000) or [OpenAPI documentation](http://localhost:8000/docs). Navigate from the market view to a sector and stock, inspect source timestamps, then initiate research using the page controls. If evidence gates block analysis, inspect the diagnostics.

## Validation

```bash
python scripts/check.py          # Static checks and change-selected tests
python scripts/check.py --full   # Full non-slow subset
pnpm --dir frontend test
pnpm --dir frontend type-check
pnpm --dir frontend build
```

Live model calls incur provider charges. Isolated tests do not replace live quality evaluation. See the [environment guide](docs/01-guides/ENVIRONMENT.md) for configuration details.

## Repository guide

- [src/](src/): data, agents, debate, memory, risk and backtesting.
- [backend/](backend/) / [frontend/](frontend/): API service and web application.
- [tests/](tests/): unit, contract and integration tests.
- [Architecture decisions](docs/05-decisions/README.md): design rationale and trade-offs.
- [Learning notes](docs/learning/README.md): explanations grounded in project code.
- [Roadmap](docs/00-overview/ROADMAP.md) / [technical debt](docs/01-guides/debt/ROUTER.md): progress and unresolved limitations.

Development uses AI-assisted coding and documentation, with records in the [work log](docs/04-changelog/logs/README.md). Technical claims should be checked against code, tests and experiment records. Most detailed project documentation is in Chinese.

[Git-validated session recovery](docs/01-guides/workflow/SESSION_RECOVERY.md) uses Git/worktree evidence as the source of truth; snapshots are validated caches.

## License

[MIT](LICENSE)
