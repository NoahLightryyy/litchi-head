# 🧠 记忆与反思模块

> Agent 历史记忆存储、检索、反思进化机制。

## 当前状态

- ✅ MemoryStore 接口（BaseStore 风格）
- ✅ JsonFileStore 实现（MVP）
- ✅ 命名空间隔离（`(type, role, user)`）
- ✅ M1 历史决策注入已接入辩论编排器
- ✅ M2 交易后反思已设计（TD-017 待实现）

## 文档

| 文件 | 说明 |
|:-----|:-----|
| [SPEC.md](SPEC.md) | 规格说明书（含争格局 + 架构对照） |
| [ADR.md](ADR.md) | 架构决策（ADR-006 三层记忆 + ADR-011 命名空间存储） |

## 对应源码

- `src/memory/store.py` — AbstractMemoryStore 接口 + JsonFileStore
- `src/memory/manager.py` — MemoryManager 高层封装
