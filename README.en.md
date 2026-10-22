# Litchi Head

**An evidence-aware multi-agent research and decision-support platform for Chinese A-share equities.**

[中文](README.md) · [Architecture decisions](docs/05-decisions/README.md) · [Module documentation](docs/03-modules/README.md) · [CI](https://github.com/NoahLightryyy/litchi-head/actions)

Python · LangGraph · Pydantic · FastAPI · Next.js · TypeScript

## Overview

Litchi Head explores how LLM-based analysis can become a traceable, testable research workflow that a human can review. It connects market, news and financial data to specialized agents, peer review, aggregation and risk assessment, then presents structured results through a web application.

The project has an implemented MVP and ongoing reliability and evaluation work. It is a personal research and engineering project. Implemented workflows do not establish investment performance or model superiority. The trading module produces plans and position calculations; live brokerage execution is not integrated.

## Engineering contributions

| Area | Implementation and trade-off | Entry point |
|---|---|---|
| Multi-agent orchestration | LangGraph coordinates analysis, strategy perspectives, peer review, independent assessment, aggregation and risk review; Pydantic validates module boundaries | [Orchestrator](src/debate/orchestrator.py), [models](src/debate/models.py) |
| Evidence validation | Cross-source market/news checks retain provenance, timestamps and diagnostics; incomplete critical evidence blocks formal debate | [Evidence service](src/data/evidence_service.py), [gate](src/debate/evidence_gate.py) |
| Auditable price data | Separates completed daily bars from provisional intraday state; implements RAW-data auditing and corporate-action adjustment verification; full production integration remains ongoing | [Contracts](src/data/kline_business.py), [adjustments](src/data/kline_adjustment.py) |
| Recoverable research | Policy research links archived evidence and citations, with SQLite task recovery, budget checks and explicit failure states | [Research service](backend/policy_research.py), [tests](tests/test_backend/test_policy_research_runtime.py) |
| Deterministic calculations | Decimal-based single-buy previews block when verified account, fee or permission context is missing | [Capital preview](backend/capital_preview.py), [contract tests](tests/test_backend/test_policy_capital_contract.py) |
| Full-stack delivery | FastAPI APIs and a Next.js interface for market discovery, sectors, stocks, charts and research status | [Backend](backend/main.py), [frontend](frontend/) |
| Feedback foundations | Research/action records, reflection, trust statistics and dynamic weighting; continuous real-outcome validation remains incomplete | [Reflection](src/debate/reflection.py), [trust](src/debate/trust.py), [memory](src/memory/) |

## Workflow

```text
Market / news / financial data
              ↓
Provenance and freshness checks → missing evidence: diagnostics / debate blocked
              ↓
Analysts → strategy perspectives → peer review → independent assessment
              ↓
Aggregation / risk review / planning → structured research → human review
              ↓
Records / reflection / trust statistics (real-outcome loop still incomplete)

FastAPI API ←→ Next.js web interface
```

Research availability and trade readiness are separate states. Displaying historical evidence or generating research does not establish that an executable order quantity can be calculated. All model calls use the shared [LLM adapter](src/utils/llm.py); the current default is `deepseek-v4-pro` with thinking disabled, governed by `DEFAULT_MODEL` in code.

## Evidence and limitations

- **Historical integration snapshot, October 1, 2026:** 1,939 Python tests passed, 4 skipped and 19 deselected; 90 frontend tests passed and the production build passed. These are historical results, not live scores for the current branch. [Validation log, Chinese](docs/04-changelog/logs/2026-10-01/2026-10-01-project-integration.md)
- **CI configuration:** Python 3.12/3.13, Ruff, Pyright, pytest, frontend tests, type checks and builds. The configured coverage threshold is 80%; a threshold is not a measured coverage result. [Workflow](.github/workflows/ci.yml)
- **Reproducibility:** isolated tests establish contract and control-flow behavior. Live data availability, paid-model quality and investment outcomes require separate validation. News coverage needs time to accumulate on a fresh deployment; unavailable upstream data can block formal debate.
- **Open work:** complete production provenance, continuous shadow evaluation, confidence calibration against real outcomes, and verified brokerage/account/fee integration. No excess-return claim or demonstrated advantage over a single-model baseline is made.

The next research step follows the [baseline and shadow-validation plan](docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md): preregistered comparisons, immutable samples and outcomes after costs. A confidence field is not an empirically validated probability of success.

## Run locally

Requires Python 3.12+. Node.js 24 and pnpm 10.33.0 match the frontend CI environment. Live AI research requires DeepSeek credentials and access to upstream data services.

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

## License

[MIT](LICENSE)
