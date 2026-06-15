# 功能模块：记忆与反思

> Agent 历史记忆存储、检索、反思进化机制。让 Agent 能从过去的正确/错误决策中学习。

## 模块定义

Agent 历史记忆存储、检索、反思进化机制。让 Agent 能从过去的正确/错误决策中学习。

**职责边界**：
- ✅ 历史决策和交易记录的持久化
- ✅ 按 namespace/语义检索相关记忆
- ✅ 交易后的自动反思 → 经验规则生成
- ✅ 记忆注入未来决策 context
- ❌ 不负责记忆的深度推理（那是辩论模块的事）
- ❌ 不负责长期趋势学习（那是因子研究模块的事）

## 代码结构

| 文件 | 说明 |
|------|------|
| `src/memory/store.py` | 存储层：MemoryStore 抽象接口 + JsonFileStore 实现（JSON/JSONL） |
| `src/memory/manager.py` | 高层封装：MemoryManager（语义化接口，隐藏 namespace 构造） |
| `src/memory/knowledge_base.py` | 金融知识库：基于 n-gram TF 向量的轻量语义检索（RAG 核心） |
| `src/memory/skill_disk.py` | 投资大师插件盘：MasterSkill（人格定义）+ SkillDisk（驱动器） |
| `src/memory/__init__.py` | 模块入口，导出所有公开 API |

**测试文件**：

| 文件 | 测试数 |
|------|:------:|
| `tests/test_memory_store.py` | 23 |
| `tests/test_memory_manager.py` | 6 |
| `tests/test_memory_knowledge_base.py` | 15 |
| `tests/test_memory_skill_disk.py` | 24 |

## 架构（当前状态）

```
┌──────────────────────────────────────────┐
│  MemoryStore（抽象接口）                   │
│  JsonFileStore（JSON/JSONL 实现）         │
│    ├─ put(key, value, namespace)          │
│    ├─ get(key, namespace)                 │
│    ├─ search(namespace, query, k)         │
│    ├─ delete(key, namespace)              │
│    ├─ list_namespaces()                   │
│    └─ list_keys(namespace)                │
├──────────────────────────────────────────┤
│  MemoryManager（封装层）                   │
│    ├─ remember(agent, type, key, value)   │
│    ├─ recall(agent, type, key)            │
│    ├─ recall_all_agents(type, k)          │
│    ├─ get_profile() / update_profile()    │
│    └─ get_session_context(agent)          │
└──────────────────────────────────────────┘

存储后端：
  data/memory/{type}/{role}/{user_id}.json    —— 单对象（working / semantic）
  data/memory/{type}/{role}/{user_id}.jsonl   —— append-only（episodic / reflective）
```

**命名空间设计**（ADR-011）：

| Namespace | 用途 |
|-----------|------|
| `("episodic", role, user)` | 情景记忆，append-only JSONL |
| `("working", role, user)` | 工作记忆，单对象 JSON |
| `("reflective", role, user)` | 反思机制，append-only JSONL |
| `("semantic", "global", user)` | 全局用户画像，单对象 JSON |

## 数据契约（关键模型）

### MemoryItem（store.py）

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | `str` | 记忆条目唯一键 |
| `value` | `Any` | 记忆内容（任意可序列化对象） |
| `namespace` | `tuple[str, ...]` | 命名空间，区分记忆类型和所属 Agent/用户 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |
| `score` | `float` | search() 相关性评分（JSON 存储默认为 0.0，向量存储返回相似度） |

### MasterSkill（skill_disk.py）

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill_id` | `str` | 唯一标识（如 "buffett"） |
| `name` | `str` | 显示名称（如 "沃伦·巴菲特"） |
| `avatar` | `str` | 头像 emoji |
| `title` | `str` | 头衔 |
| `description` | `str` | 一句话简介 |
| `tags` | `list[str]` | 标签列表（用于搜索过滤） |
| `system_prompt` | `str` | 系统提示词 —— 定义人格、语言风格、思考方式 |
| `knowledge_filter` | `str \| None` | 知识库搜索过滤词（None = 不限） |
| `enabled_by_default` | `bool` | 是否默认加载 |

## 当前实现状态

| 特性 | 状态 | 测试数 |
|:-----|:----:|:------:|
| MemoryStore 抽象接口 | ✅ 已完成 | 23（含 JsonFileStore） |
| JsonFileStore 实现（JSON/JSONL，MVP） | ✅ 已完成 | ↑ |
| 命名空间隔离（type, role, user） | ✅ 已完成 | ↑  |
| MemoryManager 语义化封装 | ✅ 已完成 | 6 |
| M1 历史决策注入（辩论编排器接入） | ✅ 已完成 | — |
| KnowledgeBase 轻量语义知识库 | ✅ 已完成 | 15 |
| SkillDisk 大师插件盘（7 位预置大师） | ✅ 已完成 | 24 |
| M2 交易后反思机制 | 🔧 已设计（TD-017 待实现） | — |
| 存储层升级（SQLite/向量数据库） | 📋 待评估 | — |

## 下一步

1. **M2 交易后反思机制** — 实现 `MemoryManager.store_decision()` / `resolve_pending()`，辩论结束时存 pending，下次同 ticker 运行时补写反思（依赖端到端链路跑通）
2. **存储层升级评估** — 记忆量 > 500 条时，启动 JSON → SQLite → 向量数据库的升级路径评估
3. **反思分析维度丰富** — 从 TradingAgents 的单维度（收益）扩展到决策质量、执行偏差、情绪影响等多维度分析

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 调研背景
