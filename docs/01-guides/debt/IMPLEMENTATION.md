# 💻 代码实现债务

> 代码实现层面的缺陷：错误处理缺失、硬编码、类型不安全等。

---

###### TD-003 MessageRouter 纯内存存储

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:core` `impact:运行时稳定` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼1h |

**描述**：
`MessageRouter._messages` 是内存 dict，进程重启全部丢失。

**利息分析**：
- Phase 0 影响不大（单次会话不跨进程）
- Phase 1 辩论系统上线后，需要持久化辩论记录

**修复方向**：
- 短期：添加 `save_snapshot()` / `load_snapshot()` JSON 持久化
- 长期：SQLite 存储

---

###### TD-006 EvidenceItem 无校验逻辑

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:core` `impact:代码质量` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼30min |

**描述**：
`EvidenceItem` 只是数据容器，无任何校验逻辑。

**修复方向**：
添加 `validate_chain()` 方法，验证来源可追溯。

---

###### TD-007 ensure_dirs() 从未被调用

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:utils` `impact:运行时稳定` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼10min |

**描述**：
`config.py` 中的 `ensure_dirs()` 函数定义了目录创建逻辑但未被调用。

---

###### TD-020 后端板块/产业链数据增强层缺失

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:backend` `impact:功能完整性` |
| **发现日期** | 2026-06-16 |
| **发现人** | AI 审视 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1.5h |

**描述**：
移除造假数据后，`backend/routers/market.py` 以下字段无真实数据源填充：
- `SectorItem.heat` / `top_stocks` — 板块热度排行和龙头股
- `SectorDetail.chain_map` — 产业链上下游映射
- `SectorDetail.ai_analysis` — AI 板块分析摘要
- `MacroBrief.risk_tips` / `hot_topics` — 市场风险提示和热点

**具体问题**：
1. ❌ akshare `stock_board_industry_name_em()` 不提供 heat/top_stocks，需从个股行情聚合计算
2. ❌ 产业链映射（上游→中游→下游）无公开 API，需接入行业数据库或知识图谱
3. ❌ 宏观风险提示无标准数据源，需接入新闻情感分析或 LLM 生成

**利息分析**：
- 前端板块详情页无数据可渲染，显示空白
- 宏观简报缺乏 hot_topics/risk_tips，信息密度低

**修复方向**：
1. `heat`：用板块内个股涨跌幅市场广度计算热度（涨幅>2%占比）
2. `top_stocks`：用板块个股排序取市值 TOP 3
3. `chain_map`：短期留空显示"待接入产业链数据源"，中期接入行业图谱
4. `ai_analysis`：T+1 批处理，LLM 总结板块表现
5. `risk_tips`/`hot_topics`：LLM 综合指数行情生成

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:utils` `impact:可部署性` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼30min |

**描述**：
模型价格硬编码在 `cost_tracker.PRICES` 类属性中。调价需改代码→重新部署。

**修复方向**：
价格表移入 `config/prices.yaml`，运行时加载。

---

###### TD-018 编排层缺少成本优化

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:debate` `impact:运行时成本` |
| **发现日期** | 2026-06-14 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼1d |

**描述**：
当前编排器对所有 ticker 跑完整的 9 层链路，无短路优化。每次约 15 次 LLM 调用，成本是竞品 1.5-2 倍。

**修复方向**：
1. 短路优化：数据为空 → 直接返回
2. 层合并：简单问题跳过分析师层
3. 模型分层：分析师用便宜模型，策略师用推理模型
