# 🧪 测试债务

> 缺少 Mock 工具、测试覆盖率不足。

---

###### TD-004 缺少测试基座和 Mock 工具

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:tests` `impact:可测试性` |
| **发现日期** | 2026-06-05 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼2h |

**描述**：
测试目录曾只有空 `__init__.py`，无实质测试，也无 Mock LLM 的工具。

**已实现**：
1. ✅ `tests/conftest.py` — 测试基座，含三个 Mock 工厂函数
2. ✅ `tests/test_sanity.py` — 24 个冒烟测试
3. ✅ `tests/test_agents_base.py` — 15 个 Agent 业务测试
4. ✅ `tests/test_core_protocol.py` — 20 个协议测试
5. ✅ `tests/test_utils_cost_tracker.py` — 15 个费用追踪测试
6. ✅ `tests/test_utils_llm.py` — 12 个 LLM 测试
7. ⬜ debate/memory/data 模块业务测试
