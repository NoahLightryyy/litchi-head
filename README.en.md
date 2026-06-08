# 🦞 Litchi Head

> Multi-Agent Investment Decision Platform — Every investor deserves their own AI research team

## What is Litchi Head?

Litchi Head is an open-source, multi-agent investment collaboration platform that brings **multi-agent collaboration**, **human-in-the-loop feedback**, and **automated analysis** together. It gives every investor — from retail to professional — access to institutional-grade investment analysis.

**The Product Philosophy (a "Grenade"):**

> Institutions have nuclear weapons (10 CFAs + Bloomberg + proprietary quant systems).
> Retail investors only have grenades — but a grenade, once you pull the pin, *works*.
>
> Our mission: investor asks one question → 15 seconds later, get a structured multi-dimensional decision card.

## Architecture

```
User Question → MasterAgent → Multi-Agent Debate → Decision Card
                    │
            ┌───────┼───────┐
         Buffett  Munger   ... (7+ master investors)
            │         │
         KnowledgeBase · SkillDisk · LLM (DeepSeek)
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Orchestration | LangGraph (StateGraph) |
| Primary LLM | DeepSeek-Chat |
| Fallback LLM | OpenAI GPT-4o-mini |
| Data Validation | Pydantic v2 |
| Frontend | Streamlit (Phase 1) |
| Data Source | akshare (Phase 1) |
| CI/CD | GitHub Actions |

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0 — Infrastructure** | ✅ **Nearly complete** | LLM layer, Agent system, KnowledgeBase, SkillDisk, LangGraph prototype |
| Phase 1 — MVP | 🔄 Upcoming | Debate engine, data feed, Streamlit frontend (3 pages) |
| Phase 2+ — Iteration | ⬜ Future | Risk module, backtesting, behavior mirror agent |

**Latest:** 228 tests passing | 8/17 technical debts closed | Urgency index: 0.7/10

## Quick Start

```bash
# 1. Clone
git clone https://github.com/changan-university/litchi-head.git
cd litchi-head

# 2. Setup environment
cp .env.example .env
# Edit .env — add your DEEPSEEK_API_KEY

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run checks
ruff check src/ tests/
pyright src/
python -m pytest
```

## Project Documentation

| Document | Description |
|----------|-------------|
| [AI Workflow](docs/流程规范/AI自动化工作流程.md) | Standard operating procedures for AI sessions |
| [Architecture Decisions](docs/技术债务与架构决策/架构决策记录.md) | ADR-001 through ADR-010 |
| [Tech Debt Log](docs/技术债务与架构决策/技术债务日志.md) | Technical debt management system |
| [Product PRD](docs/产品需求/初版要求.md) | Original product requirements |
| [Frontend MVP Spec](docs/产品需求/前端MVP需求文档-基于市场对标.md) | Market-benchmarked MVP requirements |
| [User Behavior Mirror Agent](docs/架构设计/用户行为镜子Agent设计构想.md) | Design for Phase 1+ mirror agent |
| [Knowledge Retrieval Architecture](docs/架构设计/金融知识检索架构-RAG+GREP双轨方案.md) | RAG + GREP hybrid retrieval |

## License

MIT
