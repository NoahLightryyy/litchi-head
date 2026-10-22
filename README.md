# Litchi Head · 荔枝头

**面向 A 股研究的多智能体决策支持平台：让分析过程、数据来源和证据缺口可检查。**

[English](README.en.md) · [架构决策](docs/05-decisions/README.md) · [模块文档](docs/03-modules/README.md) · [CI](https://github.com/NoahLightryyy/litchi-head/actions)

Python · LangGraph · Pydantic · FastAPI · Next.js · TypeScript

## 项目简介

Litchi Head 探索一个具体问题：如何把大语言模型的多角度分析组织成可追溯、可检验、可由人审阅的投资研究流程？项目将行情、新闻与财务数据接入多智能体工作流，通过独立分析、同侪复核、聚合与风控生成结构化研究结果，并在 Web 界面展示。

当前阶段为 **MVP 已实现、可靠性与评测持续完善**。这是个人研究与工程项目；已经实现的工作流不代表投资收益或模型优势已经得到验证。交易执行模块目前提供计划与仓位计算，尚未接入实盘券商自动下单。

## 核心工程工作

| 方向 | 实现与设计取舍 | 代码入口 |
|---|---|---|
| 多智能体编排 | LangGraph 状态图串联分析、策略观点、互评、独立评审、聚合与风控；Pydantic 约束跨模块输出 | [辩论引擎](src/debate/orchestrator.py)、[数据模型](src/debate/models.py) |
| 数据证据与门禁 | 多源行情/新闻对账，保留来源、时间与失败诊断；关键证据不完整时阻断正式辩论 | [证据服务](src/data/evidence_service.py)、[辩论门禁](src/debate/evidence_gate.py) |
| K 线审计 | 区分已完成日线与盘中临时状态；实现 RAW 数据审计、公司行动与复权核验，完整生产链路仍在接入 | [K 线业务契约](src/data/kline_business.py)、[复权模块](src/data/kline_adjustment.py) |
| 可追踪研究任务 | 政策研究关联归档材料与引用，支持 SQLite 任务恢复、预算检查及明确失败状态 | [政策研究服务](backend/policy_research.py)、[专项测试](tests/test_backend/test_policy_research_runtime.py) |
| 确定性金额计算 | 使用 Decimal 计算单笔买入预览；缺少已核验账户、费用或权限上下文时返回阻断状态 | [本金预览](backend/capital_preview.py)、[契约测试](tests/test_backend/test_policy_capital_contract.py) |
| 全栈交付 | FastAPI 提供结构化 API，Next.js 展示市场、板块、个股、图表与研究状态 | [后端](backend/main.py)、[前端](frontend/) |
| 结果反馈基础 | 保存研究与操作记录，提供反思、信任度统计和动态权重机制；连续真实结果验证尚未完成 | [反思](src/debate/reflection.py)、[信任度](src/debate/trust.py)、[记忆层](src/memory/) |

## 主线已整合的能力

主线还包含三源指数核验、分时百分比轴与量额副图、公司解读阶段错误、行业选股搜索、可追溯产业地图，以及 [E0 离线评测基础设施](src/backtest/e0/)。E0 的采样、运行与结果存储已实现，尚未据此证明模型优势。

## 工作流

```text
行情 / 新闻 / 财务数据
          ↓
来源与时间校验 → 证据不足：明确诊断 / 阻断正式辩论
          ↓
分析师 → 策略观点 → 同侪复核 → 独立评审与聚合
          ↓
风控 / 交易计划 → 结构化研究结果 → 人工审阅
          ↓
记录 / 反思 / 信任度统计（真实结果闭环仍待完善）

FastAPI API ←→ Next.js Web 界面
```

研究展示与交易就绪状态分开：能够展示历史材料或生成研究，不意味着可以生成可执行交易数量。模型统一经过 [LLM 适配层](src/utils/llm.py)；当前默认是 `deepseek-v4-pro` 非思考模式，以代码中的 `DEFAULT_MODEL` 为准。

## 验证证据与当前边界

- **历史集成验收（2026-10-08）**：本地检查记录为 Python 2,371 项通过、7 项跳过、19 项排除；前端 141 项通过，生产构建通过。该数字对应当时的集成快照，不是当前分支的实时成绩。[验收记录](docs/04-changelog/logs/2026-10-08/2026-10-08-branch-consolidation.md)
- **持续集成配置**：Python 3.12/3.13、Ruff、Pyright、pytest，以及前端测试、类型和构建检查；覆盖率门禁配置为 80%，不把门槛当成实测覆盖率。[工作流](.github/workflows/ci.yml)
- **可复现边界**：离线测试可验证契约与控制流程；真实数据可用性、付费模型质量和投资效果需要分别验证。首次部署的新闻缓存需要积累覆盖窗口，部分上游不可用时正式辩论可能被阻断。
- **尚未完成**：完整生产数据血缘、连续影子验证、真实结果上的置信度校准、券商账户与费用证明接入。没有声称获得超额收益，也没有声称多智能体优于单模型基线。

研究评估下一步是按 [Baseline 与影子验证计划](docs/02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)，使用预注册对照、不可变样本与成本后结果检验系统价值。置信度字段的存在不代表它已经是真实胜率。

## 本地运行

需要 Python 3.12+；前端建议与 CI 一致使用 Node.js 24、pnpm 10.33.0。真实 AI 研究还需要 DeepSeek 凭据与可访问的数据源。

```bash
git clone https://github.com/NoahLightryyy/litchi-head.git
cd litchi-head
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env      # PowerShell: Copy-Item .env.example .env

# 交互式写入系统凭据管理器，不把密钥提交到仓库
python scripts/store-api-keys.py --set DEEPSEEK_API_KEY

corepack enable
corepack prepare pnpm@10.33.0 --activate
pnpm --dir frontend install --frozen-lockfile
```

在仓库根目录分别启动两个终端：

```bash
# 终端 1（已激活 Python 环境）
python -m uvicorn backend.main:app --reload --port 8000

# 终端 2
pnpm --dir frontend dev
```

打开 [Web 界面](http://localhost:3000) 或 [OpenAPI 文档](http://localhost:8000/docs)。从市场榜单进入板块和个股，查看数据时间与来源，再按页面提示发起研究。数据门禁未满足时应查看诊断，不能把阻断当成“无风险”结论。

## 开发验证

```bash
python scripts/check.py          # 静态检查 + 按改动选择测试
python scripts/check.py --full   # 完整非慢测子集
pnpm --dir frontend test
pnpm --dir frontend type-check
pnpm --dir frontend build
```

真实模型调用涉及供应商费用；常规隔离测试不能代替实网质量验收。环境和数据源细节见 [环境指南](docs/01-guides/ENVIRONMENT.md)。

## 仓库导航

- [src/](src/)：数据、Agent、辩论、记忆、风控和回测模块。
- [backend/](backend/) / [frontend/](frontend/)：API 服务与 Web 应用。
- [tests/](tests/)：契约、单元与集成测试。
- [架构决策记录](docs/05-decisions/README.md)：选型理由与权衡。
- [学习卡片](docs/learning/README.md)：结合实际代码解释关键技术。
- [路线图](docs/00-overview/ROADMAP.md) / [技术债务](docs/01-guides/debt/ROUTER.md)：进度与未解决问题。

开发过程中使用 AI 辅助编码与文档整理，相关工作日志保留在 [changelog](docs/04-changelog/logs/README.md)。技术结论应通过代码、测试与实验记录核查。

[Git 校验的会话恢复](docs/01-guides/workflow/SESSION_RECOVERY.md)：Git/worktree 是恢复依据，会话快照仅作为校验后的缓存。

## License

[MIT](LICENSE)
