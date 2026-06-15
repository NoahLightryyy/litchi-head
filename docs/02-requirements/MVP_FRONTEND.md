# Frontend MVP Requirements Document

> 2026-06-07 | Related: ADR-004 (Streamlit MVP Frontend) | `docs/architecture-design/user-behavior-mirror-agent-design-concept.md`
> Method: Research TradingAgents (70k stars) / AI Hedge Fund (51k stars) / Vibe-Trading (9.3k stars) frontends, extract commonalities + filter by "grenade" positioning

---

## Table of Contents

- [1. Competitive Frontend Research Results](#1-competitive-frontend-research-results)
- [2. "Grenade" Filter: What We Do, What We Don't](#2-grenade-filter-what-we-do-what-we-dont)
- [3. Phase 1 MVP Page Planning](#3-phase-1-mvp-page-planning)
- [4. Detailed Page Design](#4-detailed-page-design)
- [5. Frontend Data Contracts](#5-frontend-data-contracts)
- [6. Relationship with Backend](#6-relationship-with-backend)
- [7. Phased Implementation Plan](#7-phased-implementation-plan)

---

## 1. Competitive Frontend Research Results

### 1.1 Three Competitors' Frontend Solutions

| Project | Stars | Frontend Tech Stack | Core Interface Style |
|:----|:-----:|:--------------------|:---------------------|
| **TradingAgents** | 70k stars | Original CLI + Rich; China fork: **Streamlit** (rapid prototype) and **Vue 3 + FastAPI** (production SPA) | Form input + decision card + progress bar + report export |
| **AI Hedge Fund** | 51k stars | **React 18 + React Flow** (drag-and-drop Agent workflow editor) | Multi-panel workspace + node visualization + SSE real-time stream |
| **Vibe-Trading** | 9.3k stars | **React 19 + Vite + ECharts** (non-Streamlit) | Chat-style interaction + backtest metric cards + chart display |

### 1.2 Common Interface Features (present in all three competitors)

| Common Feature | TradingAgents | AI Hedge Fund | Vibe-Trading | Description |
|:--------------|:-------------:|:-------------:|:------------:|:------------|
| **Decision card output** | ✅ Color-coded BUY/SELL/HOLD | ✅ Node result popup | ✅ Strategy card | Decision card is the core output form across all competitors |
| **Real-time reasoning stream** | ✅ Streamlit progress bar 0-100% | ✅ SSE streaming Agent reasoning | ✅ Step-by-step display | Users want to see the Agent "thinking" |
| **Multi-panel layout** | ✅ Sidebar + main area | ✅ VSCode-style multi-panel | ✅ Sidebar + main area | Not a single page, has navigation structure |
| **Dark mode** | ✅ | ✅ | ✅ | Standard for financial applications |
| **Agent status indicator** | ✅ Progress step labels | ✅ Color-coded IDLE->RUNNING->DONE | ✅ Execution step indicator | Users want to know "what step are we on" |
| **Report export** | ✅ Markdown/DOCX/PDF | ❌ None | ❌ None | Common need for paying users |

### 1.3 Differentiated Features (single competitor unique)

| Feature | Source Project | Description | Will We Adopt? |
|:-------|:--------------|:------------|:--------------|
| **Drag-and-drop Agent workflow editor** | AI Hedge Fund | React Flow drag-and-drop connections | ❌ No. This is for quant researchers, not retail investors |
| **Backtest metric visualization** (Sharpe/drawdown/win rate cards) | Vibe-Trading | Backtest result display | ❌ Not in Phase 1. We don't have a backtest engine |
| **Chat-style interaction** | Vibe-Trading | User types -> Agent responds | Warning. Considering. Matches the educational dialogue scenario with Xiao Zhi Agent |
| **Multi-Agent parallel progress bar** | TradingAgents | 0-100% showing debate progress | ✅ Yes. Simple and practical, users can perceive "the system is working" |
| **Export PDF/DOCX report** | TradingAgents | Analysis report export | ✅ Phase 2. Parents may want to save analysis results |

---

## 2. "Grenade" Filter: What We Do, What We Don't

### 2.1 Filtering Principles

```
✅ Must do: Retail investors can understand in 15 seconds -> complete a decision
✅ Can do: Parents would use -> improve practicality
❌ Don't do: Only quant researchers would use -> increases complexity
❌ Don't do: Needs backtesting/live trading to display -> no backend support yet
```

### 2.2 Our Frontend Positioning

```diff
- AI Hedge Fund style: drag-and-drop workflow editor, VSCode multi-panel, high technical barrier
- Vibe-Trading style: backtest charts, factor analysis, quant tools

+ Our style: "Decision Card" -- fast, clear, everything visible on one screen
+ Reference prototype: TradingAgents' Streamlit branch (form + decision card + progress bar)
+ But simpler: remove technical parameter configuration, focus on "input stock -> see analysis -> make decision"
```

### 2.3 Do/Don't List

| Feature | Do? | Reason |
|:-------|:---:|:------|
| Homepage: market indices + quick entry | ✅ Phase 1 | First screen parents see when opening |
| Analysis page: input stock -> master analysis | ✅ Phase 1 | Core functionality |
| Decision card: comprehensive judgment + dimensional analysis | ✅ Phase 1 | Product's core output form |
| Multi-Agent parallel progress bar | ✅ Phase 1 | User perceives "analysis in progress" |
| Dark mode | ✅ Phase 1 | Standard for financial apps |
| My page: Mirror Agent | ✅ Phase 1+ | Frontend entry for Mirror Agent |
| Export PDF report | Paused Phase 2 | Valuable but not urgent |
| Drag-and-drop Agent workflow | ❌ Never | Conflicts with "grenade" positioning |
| Backtest charts | ❌ Not Phase 1 | Backend backtest engine not yet written |
| Chat-style interaction (educational Xiao Zhi) | Paused Phase 2 | Needs backend educational Agent support |
| Live trading interface | ❌ Not Phase 1 | No live trading integration |

---

## 3. Phase 1 MVP Page Planning

### 3.1 Page Structure

```
Navigation bar (3 Tabs):
  +----------+----------+----------+
  | Market   | Analyze  | Profile  |
  +----------+----------+----------+
```

Just 3 pages. No more. Parents don't need to learn a complex navigation structure.

### 3.2 Page Overview

| Page | Route | Core Function | Complexity | Priority |
|:----|:------|:--------------|:----------:|:--------:|
| **Home: Market** | `/` | Market indices + hot stocks + quick entry | Two stars | Gold |
| **Analysis page** | `/analysis?ticker=Moutai` | Input stock -> Master analysis -> Decision card | Four stars | Gold |
| **Profile** | `/profile` | Mirror Agent + history + settings | Two stars | Silver |

### 3.3 Page Flow

```
Homepage --click stock--> Analysis page
                               |
                          Analysis complete
                               |
                               v
                         Decision card display
                               |
                    +----------+----------+
                    v                     v
              Back to home         Profile page (Mirror Agent)
```

---

## 4. Detailed Page Design

### 4.1 Homepage: Market (`/`)

```
+-------------------------------------------------+
| Market                                    Dark   |
|                                                     |
|  Shanghai Composite   Shenzhen Component   ChiNext  |
|  3,168.42             9,712.35            1,856.20  |
|  Up +0.68%           Down -0.23%         Up +1.02% |
|                                                     |
|  ---- Hot Stocks ----                               |
|  +-----------------------------------------------+ |
|  | Kweichow Moutai  600519    1,685.00  Up 2.3%  | |
|  | CATL             300750    218.50    Down 0.8%  | |
|  | Tencent          00700.HK  380.20    Up 1.5%   | |
|  | ...See more >>                                  | |
|  +-----------------------------------------------+ |
|                                                     |
|  Quick Analysis                                     |
|  +------------------------------------------------+|
|  | Enter stock name or code                       ||
|  +------------------------------------------------+|
|                                        [Start Analyze]|
+-------------------------------------------------+
```

**Description**:
- Market index data source: akshare (Phase 1 pulls directly from akshare, no backend cache needed)
- Hot stocks: initially fixed list, doesn't depend on backend recommendations
- Search box: enter stock name or code -> navigate to analysis page
- Dark mode: dark by default (financial app convention), toggleable

**Backend requirements**:
- No backend interface needed; index data directly calls akshare from frontend (or initial mock data)
- Search box: local stock code mapping table (JSON file, about 3000 common A-share stocks)

---

### 4.2 Analysis Page (`/analysis?ticker=Moutai`)

This is the **core page**, the direct embodiment of the "grenade" value.

```
+-------------------------------------------------+
| <- Back                                           |
|                                                     |
|  Kweichow Moutai (600519)  1,685.00  Up 2.3%       |
|                                                     |
|  Analysis in progress...                            |
|  ==================== 60%                           |
|  +-- Checkmark Buffet     Analysis complete         |
|  +-- Spinner Lynch        Analyzing...              |
|  +-- Hourglass Dalio      Waiting                   |
|  +-- Hourglass Graham     Waiting                   |
|                                                     |
|  ---- Displayed when all complete ----              |
|                                                     |
+-------------------------------------------------+

                 v All complete

+-------------------------------------------------+
|  <- Back                                          |
|                                                     |
|  Kweichow Moutai (600519)  1,685.00  Up 2.3%       |
|                                                     |
|  Card Comprehensive: Caution Hold (Confidence 65%)  |
|                                                     |
|  +-----------------------------------------------+ |
|  | Buffet     Green Reasonable valuation          | |
|  |            PE 35x > historical median 28x      | |
|  |            Insufficient margin of safety       | |
|  +-----------------------------------------------+ |
|  | Lynch      Red Atypical growth stock           | |
|  |            PEG 1.8, growth slowing             | |
|  |            Recommend wait and see              | |
|  +-----------------------------------------------+ |
|  | Dalio      Yellow Late cycle                   | |
|  |            Credit contraction signal           | |
|  |            Need to reduce position             | |
|  +-----------------------------------------------+ |
|                                                     |
|  Core Disagreement: Valuation school vs Macro school |
|   Buffet sees valuation as reasonable               |
|   Dalio sees macro environment as requiring caution  |
|                                                     |
|  One sentence: Not cheap now, but hold for 5+ years  |
|  Can wait for pullback to 1400 to build position     |
|                                                     |
|  +--------------+  +--------------+                  |
|  | Detailed Report| |  Analyze Another|              |
|  +--------------+  +--------------+                  |
+-------------------------------------------------+
```

**Description**:
- **Progress bar phase**: Shows each Agent's analysis status, letting users perceive "the system is working"
- **Decision card phase**: This is the core output, displayed completely within one screen
- Each master takes one row, can independently expand/collapse detailed reasoning
- "Core Disagreement" and "One Sentence" are results aggregated by the debate engine
- All competitors have similar decision card forms -- this is industry consensus

**Backend requirements** (needs existing backend to provide):
- `POST /api/analyze` -> trigger analysis process -> return session_id
- `GET /api/analyze/{session_id}/status` -> each Agent's progress
- `GET /api/analyze/{session_id}/result` -> final DebateState result

---

### 4.3 Profile Page (`/profile`)

```
+-------------------------------------------------+
| Profile                                          |
|                                                     |
|  ---- Mirror Agent ----                            |
|  Your Investment Behavior Analyst                  |
|  ================        Understanding 30%         |
|  3 investment behaviors recorded                   |
|                                                     |
|  [View Detailed Analysis ->]                       |
|                                                     |
|  ---- History ----                                 |
|  +-----------------------------------------------+ |
|  | 2026-06-07  Moutai   Caution Hold =======     | |
|  | 2026-06-05  Wuliangye Active Buy ===          | |
|  | 2026-06-01  Tencent   Wait and See =========  | |
|  +-----------------------------------------------+ |
|                                                     |
|  Settings                                           |
|  [x] Notify when analysis is complete              |
|  [ ] Enable Mirror Agent (available after graduation)|
+-------------------------------------------------+
```

**Backend requirements**:
- `GET /api/history` -> user's historical analysis records
- `GET /api/mirror/profile` -> Mirror Agent current understanding/stats (Phase 1+)

---

## 5. Frontend Data Contracts

This is the **backbone** -- the interface protocol between frontend and backend. Once these are set, AI can separately fill in the frontend and backend details.

### 5.1 Analysis Request/Response

```python
# ========= Request =========

class AnalysisRequest(BaseModel):
    """User initiates an analysis"""
    ticker: str                                  # "600519" or "Kweichow Moutai"
    market: str = "A"                            # "A" / "HK" / "US"

# ========= Progress =========

class AgentProgress(BaseModel):
    """Single Agent's analysis progress"""
    agent_name: str                              # "Buffett" / "Lynch"
    status: Literal["pending", "running", "completed", "error"]
    progress_pct: float = 0.0                    # 0-100
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

class AnalysisStatus(BaseModel):
    """Analysis progress query response"""
    session_id: str
    overall_status: Literal["running", "completed", "error"]
    overall_progress: float                       # 0-100
    agents: list[AgentProgress]
    started_at: str
    estimated_remaining_sec: int | None = None    # Optional

# ========= Result =========

class MasterOpinion(BaseModel):
    """Single master's opinion -- one row of the decision card"""
    master_name: str                              # "Buffett"
    signal: Literal["bullish", "bearish", "neutral", "caution"]
    signal_label: str                             # "Green Reasonable valuation" / "Red Atypical growth stock"
    signal_icon: str = ""                         # "Green" / "Red" / "Yellow"
    confidence: float                             # 0.0-1.0
    reasoning: str                                # Core logic in one sentence
    detail: str = ""                              # Detailed reasoning (expandable)
    evidence: list[str] = field(default_factory=list)  # "PE 35x > historical median 28x"

class AnalysisResult(BaseModel):
    """Complete result of one analysis -- data source for decision card"""
    session_id: str
    ticker: str
    ticker_name: str                              # "Kweichow Moutai"
    price_current: float
    change_pct: float
    
    # Comprehensive judgment
    verdict: str                                  # "Caution Hold"
    verdict_signal: Literal["positive", "caution", "negative", "neutral"]
    verdict_confidence: float                     # 0.65
    
    # Each master's opinion
    opinions: list[MasterOpinion]
    
    # Debate summary
    core_disagreement: str = ""                   # "Valuation school vs Macro school"
    one_sentence: str = ""                        # One-sentence recommendation
    
    # Metadata
    analyzed_at: str
    agents_used: int                              # Number of masters participating in analysis
    total_latency_ms: float = 0.0
```

### 5.2 History

```python
class HistoryItem(BaseModel):
    """One historical analysis record"""
    session_id: str
    ticker: str
    ticker_name: str
    date: str
    verdict: str
    verdict_signal: str
    verdict_confidence: float

class HistoryResponse(BaseModel):
    """History record list"""
    items: list[HistoryItem]
    total: int
```

### 5.3 Frontend Local Data (no backend needed)

```python
# Frontend local stock code mapping table
# Structure: dict[str, StockInfo]
class StockInfo(BaseModel):
    """Used for search box autocomplete"""
    code: str                                     # "600519"
    name: str                                     # "Kweichow Moutai"
    market: str                                   # "A" / "HK" / "US"
    sector: str = ""                              # "Baijiu"

# Storage location: JSON file within the frontend project
# data/stocks.json -- about 3000 A-shares + 200 HK/US Chinese stocks
```

---

## 6. Relationship with Backend

### 6.1 Phase 1 Data Flow

```
User enters "Moutai" in search box
    |
    v
Frontend (Streamlit)
    | 1. Match to "600519" from local stocks.json
    | 2. POST /api/analyze -> backend triggers analysis
    | 3. Poll GET /api/analyze/{id}/status -> display progress bar
    | 4. GET /api/analyze/{id}/result -> display decision card
    |
    v
Backend (Python)
    +-- MasterAgent schedules 7 master Agents
    +-- Masters analyze in parallel
    +-- Debate engine aggregates -> returns AnalysisResult
```

### 6.2 What Can Be Done In Advance for Phase 1 (even if backend isn't ready)

| Frontend Part | Backend Ready? | What to Do? |
|:--------------|:---------------|:------------|
| Homepage market indices | No data/ module empty | Frontend uses mock data first, mock API |
| Search box + stock matching | Yes stocks.json is frontend local data | No backend dependency |
| Decision card display | Warning Debate engine not written | Hardcode a sample AnalysisResult first, build UI |
| Progress bar | Warning Backend API not determined | Simulate progress animation |
| Mirror Agent page | No Mirror Agent not implemented | Leave placeholder, show "Coming Soon" |

### 6.3 Frontend and Backend Division of Labor

```
Frontend (Streamlit) manages:
  - Page layout and display
  - User input and interaction
  - Local stock data (stocks.json)
  - Calling backend API for analysis results
  - Calling akshare for index quotes (Phase 1 temporary solution)

Backend (existing src/) manages:
  - Receiving analysis requests -> scheduling Agents
  - Maintaining debate state (DebateState)
  - Returning structured AnalysisResult
  - User history storage and query
```

---

## 7. Phased Implementation Plan

### Phase 1 MVP (Before July)

| Step | Page | Estimate | Prerequisites |
|:----:|:-----|:--------:|:--------------|
| 1 | Project skeleton -- Streamlit + page routing + dark theme | 2h | None |
| 2 | Homepage -- market indices + hot stocks + search box | 3h | stocks.json data |
| 3 | stocks.json -- A-share 3000 stock code mapping | 1h | None |
| 4 | Analysis page progress bar -- Agent status display component | 2h | AnalysisStatus data model |
| 5 | Decision card component -- MasterOpinion display + comprehensive judgment | 3h | AnalysisResult data model |
| 6 | Analysis page complete flow -- input -> wait -> display | 2h | Backend analysis API (at least mock) |
| 7 | Profile page -- history + Mirror Agent placeholder | 2h | Backend history API |
| 8 | End-to-end integration -- frontend connected to real backend | 2h | Debate engine at least running minimal prototype |

**Total: approx 15-17 hours (if AI writes frontend, 2-3 calendar days)**

### Phase 2 (After MVP Validation)

| Item | Description |
|:----|:------------|
| Mirror Agent full page | Behavior comparison report visualization |
| Educational Xiao Zhi dialogue interface | Chat-style interaction |
| Export PDF report | reportlab or WeasyPrint |
| Decision card sharing | Generate shareable image |
| Detailed Agent reasoning expansion | Collapse/expand each master's full reasoning chain |

---

## Changelog

| Date | Action | Description |
|:----|:-------|:------------|
| 2026-06-07 | Created | MVP requirements document based on TradingAgents / AI Hedge Fund / Vibe-Trading frontend research |
