# 第一步能力盘点：政策、标的与本金执行

日期：2026-10-18。S1完成。基线：`codex/integration-project-20261001`，HEAD `8f92a50`，**包含当前未提交工作树**，不能仅凭HEAD复现全部能力。由数据、AI运行、本金三个只读子任务并行查代码，主窗口复核关键路径；未读取真实账户/研究历史/凭证，未进行新实网调用或付费模型评测。代码存在不等于来源当前可用或已达生产验收。

## 结论与下一阶段阻塞

可复用的是新闻检索、公司研究采集、身份行情、部分持久化与页面容器；**政策到标的的证据链、ETF穿透、账户约束下的精确执行计算尚未形成闭环**。S2可启动证据获取与规则样例；S3契约和前端真实模式仍未冻结。

最先处理：①央视报道→政策原文→片段定位；②公司业务与ETF指数/持仓覆盖；③账户/交易规则/费用的确定性契约；④新研究任务的版本、预算和恢复语义。已有6题评测不是这些能力的验收。

所有代码路径相对仓库根目录；函数名用于可复查定位。

## 能复用（限定用途）

| ID | 现有能力 / 代码证据 | 可复用部分 | 不可据此声称 | 负责人 |
|---|---|---|---|---|
| R01 | `src/data/news_archive.py::NewsArchive.query`、`backend/routers/news_archive.py::archived_news` | 六渠道归档、日期/关键词/分页与缺口 | 已有央视直连、连续完整历史 | PC-01A |
| R02 | `src/data/news_context.py::format_news_context` | 新闻去重、渠道均衡与出处上下文 | 摘要等于全文、转载等于独立验证 | PC-01A/03 |
| R03 | `src/data/evidence.py`、`evidence_service.py::DataEvidenceService` | 来源状态、证据信封的设计与校验模式 | 现成政策领域契约 | PC-08 |
| R04 | `backend/company_research.py::fetch_evidence/parse_profile/parse_report` | 主营、年报半年报节选、公司身份及日期、缺口 | 公司完整披露、订单/分部收入已取得 | PC-01B |
| R05 | `backend/routers/company_research.py`、`CompanyInterpretation/CitedInsight/StockImpact` | 事实/推断与条件影响的结构、GET/POST读取生成 | 政策关联已校验 | PC-03/08 |
| R06 | `backend/company_research.py::validate_citations/CompanyResearchStore` | 引用ID白名单、校验和、成功结果保存 | 语义支持验证、历史版本或运行续接 | PC-04/08 |
| R07 | `src/data/fundamental_research.py::get_fundamental_research` | 合并财务事实与确定性指标 | 政策相关业务收入占比 | PC-01B |
| R08 | `src/data/providers/cninfo.py::CninfoDirectAnnouncementSource/CninfoAnnouncementSource` | 公告元数据适配器和附件URL结构 | 生产研究入口已接线、正文已提取 | PC-01B |
| R09 | `backend/routers/discovery.py`、`backend/routers/market.py`、`eastmoney_boards.py` | ETF目录与来源内板块成分、代码绑定 | 分类成员就一定受政策影响 | PC-01B |
| R10 | `backend/etf_contract.py::EtfIdentity/EtfQuote/EtfDetail`、`routers/etfs.py` | ETF身份、市场、报价时间、缺口 | 已有指数、持仓、交易规则；契约是display-only | PC-01B/08 |
| R11 | `src/utils/llm.py::LLMService.invoke_structured/ainvoke` | 统一模型入口、Pydantic输出、有限重试 | 完整调用审计与硬预算闸门 | PC-10 |
| R12 | `backend/debate_research.py::collect_research_context/supplement_research` | 主动补证、上下文长度/超时/身份控制 | 政策原文关联已实现 | PC-02/03 |
| R13 | `src/debate/orchestrator.py::_run_independent_review`、`research_evidence.py` | 独立复核、研究证据与交易准入分开 | 多角色共识等于事实核验 | PC-02 |
| R14 | `src/debate/session_store.py::SqliteDebateSessionStore` | 会话持久化、状态和结果读取模式 | 服务重启能自动续跑 | PC-04/08 |
| R15 | `src/utils/cost_tracker.py::CostTracker`、`scripts/evaluate_research_smoke.py` | 用量/费用估算；manifest、哈希、严格评分样例 | 费用即账单、6题等于投资效果、局部预算等于全局闸门 | PC-07/10 |
| R16 | `frontend/components/research/research-context.tsx`及四类详情页 | 标的上下文、内嵌对照容器 | 已有关联研究或执行结果 | PC-09 |
| R17 | `capital-comparison.tsx`、`frontend/lib/capital-scenarios.ts` | 输入校验、表格、金额格式与演示测试 | 可直接当真实资金配置或订单计算器 | PC-05/06/09 |
| R18 | `frontend/lib/portfolio.ts::Holding/portfolioSummary`、`hooks/use-holdings.ts` | 用户手填持仓、本机保存与存储错误保护 | 完整账户、实际可卖数量、ETF穿透 | PC-05/09 |
| R19 | `src/risk/models.py`、`src/trader/models.py`、`src/backtest/models.py` | 研究结果结构与测试组织参考 | 已有账户硬约束或实盘执行计算 | PC-05/06/07 |

## 要修复 / 加固（不能原样作为新闭环）

| ID | 具体事实与证据 | 修复验收 | 归属/优先级 |
|---|---|---|---|
| F01 | `policy-sample.tsx`和`research-context.tsx`为历史样例/待核验提示；本金固定60/20/20、3000元最低订单 | 真实模式由研究/约束结果驱动，演示保持独立标识 | PC-09；S6 |
| F02 | `providers/news.py::_association_reason`与归档检索为名称/代码命中 | 命中仅召回，关联必须有业务与原文证据 | PC-01A/03；S2–4 |
| F03 | CNINFO适配器存在，但src/backend搜索未见生产构造消费链 | 接线、正文可得状态、超时/覆盖传播、测试 | PC-01B/08；S2 |
| F04 | `parse_report`为限长节选，`validate_citations`只验证引用ID | 原文片段身份、偏移/页码、逐声明支持与反证检查 | PC-01B/03/11；S2–4 |
| F05 | `CompanyResearchStore.save`按代码覆盖，草图key不含证据版本 | 不可变快照、输入指纹、更新失效、历史可追溯 | PC-04/08；S3 |
| F06 | 公司/草图`_busy`为进程内set；`recover_interrupted`把任务置失败 | 新研究明确幂等/任务状态/恢复和费用语义，不能许诺自动续跑 | PC-08/10；S3 |
| F07 | CostTracker事后记录，10元预留只在smoke；结构化parsing_error在记用量前抛错 | 新研究调用前预算预留；失败调用也审计用量，待针对性测试 | PC-10；S3，PC-AUDIT-003 |
| F08 | Holding只有手填市值/成本，行业自填，缺现金/数量/可卖量 | 新约束输入明确完整性、身份和缺项；旧记录不可直接推导余额 | PC-05/08/09；S3–5 |
| F09 | 风险官输入为代码/问题/研究文本；阈值在prompt | 程序硬约束；AI只解释，不把prompt百分比变为用户默认 | PC-05/03；S5 |
| F10 | `ExecutionStep.quantity_pct`写占总资金，但bridge再乘总仓位；非hold写buy、固定整百股、不留费用 | 冻结比例/方向/单位规则后测试，不直接复用为订单计算器 | PC-06/11；PC-AUDIT-002 |
| F11 | `BacktestEngine.run`收入用请求数量、扣仓用min数量，max_single_position未执行 | 超量卖出/部分成交/失败入场等回归，避免错误收益进榜 | PC-07/11；PC-AUDIT-001 |

F10/F11是代码审查发现，尚未运行行为复现；登记为待评估，不宣称已修复。F07失败用量路径同样需测试确认实际影响。其余为本计划显式补齐任务，不把所有新增能力重复登记为缺陷。

## 需要新增（按最小可交付顺序）

| ID | 新能力 | 最小交付与依赖 | 主责 |
|---|---|---|---|
| N01 | 央视与政策原文入口 | 报道URL/时间/内容状态；政策文号/发布机关/成文发布生效时间分离；S2 | PC-01A |
| N02 | 政策证据片段契约 | source/document/fragment/claim身份、版本、原文定位、支持/反驳/不足；S3冻结 | PC-08/03 |
| N03 | 公司兑现证据 | 业务分部收入、订单与报告期、单位及缺口；未披露不能填零 | PC-01B |
| N04 | ETF指数与持仓证据 | 官方指数身份、报告期/披露日、持仓权重及覆盖率；前十大非全量 | PC-01B/08 |
| N05 | 政策研究和专项复核 | 相关/无关/不足、传导假设、兑现条件、反证；消费N02–04 | PC-03/02 |
| N06 | 用户执行约束 | 本金/现金/数量/持仓完整性/期限/可承受金额损失；无隐式风险默认 | PC-05/08 |
| N07 | 证券规则及费用快照 | 身份、买卖单位/增量、权限、费用方向和有效日期、来源；S2取样S3冻结 | PC-06/01B |
| N08 | 确定性执行计算器 | Decimal/整数金额、可买数量/费用/剩余现金/缺项阻断；不下单 | PC-06/08 |
| N09 | 重复暴露与压力 | 股票+ETF身份去重、缺失权重非零；情景损失及违反约束原因 | PC-05 |
| N10 | 研究任务与版本服务 | 幂等、预算、持久状态、有限重试、失败恢复、版本失效及审计 | PC-08/04/10 |
| N11 | 真实同页对照 | 证据/判断/约束/下一步；板块不得给出可买股数 | PC-09，🔒 待契约 |
| N12 | 政策/执行评测集 | 正反例、时间错配、缺披露、费用不足、ETF覆盖不全、故障恢复；不能沿用6题结论 | PC-07/11 |

## 下一批可并行任务及交接

1. PC-01A：从六渠道新闻做候选召回，验证央视原页与政策原文可取性，交付一个带定位的证据包。
2. PC-01B：核对BK0917成分与一家候选公司业务、相关ETF官方指数/持仓及交易规则，记录缺口后选首批。
3. PC-08/04/10：基于盘点先写证据身份、版本、任务预算契约草案；以S2真实样例冻结，不能先编造字段上线。
4. PC-05/06：准备账户约束和交易单位/费用边界样例，拆出F10/F11修复；未解决前新计算器不依赖其输出。
5. PC-07/11：设计固定正反例与失败矩阵，预留独立验收样本。

本轮3个只读子任务已全部完成，无修改冲突；文档由主窗口统一维护。下一批可写并行必须先整理依赖基线，再建立独立worktree。未启动S2采集、未新增API、未改前端或风险默认值。
