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

###### TD-008 cost_tracker 模型价格硬编码

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
