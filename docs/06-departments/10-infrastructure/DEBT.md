---
department: 基础设施部
---

# 🐛 基础设施部债务清单

> 本文件只列基础设施部（`src/utils/`）的债务。

---

## 开放债务

| ID | 标题 | 严重度 | 类型 | 状态 |
|:---|:-----|:------:|:----|:----|
| TD-001 | LLM 封装层 — 模型路由待补完 | 🟡 moderate | 功能缺失 | 🔧 修复中 |
| TD-005 | 双配置源未协调 | 🟡 moderate | 架构设计 | 📋 待评估 |
| TD-007 | ensure_dirs() 从未被调用 | 🟢 low | 缺陷 | 📋 待评估 |
| TD-008 | cost_tracker 价格硬编码 | 🟢 low | 代码质量 | 📋 待评估 |
| TD-038 | `.env` 明文存储 API 密钥 | 🔴 critical | 安全 | 📋 待评估 |
| TD-040 | LLM Provider fallback 链缺失 | 🟡 moderate | 功能缺失 | 📋 待评估 |
| TD-055 | 价格硬编码（与 TD-008 同源） | 🟢 low | 代码质量 | 📋 待评估 |

## 已关闭债务

| ID | 标题 | 修复日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-009 | CI 迁移 GitHub Actions | 2026-06-06 | 创建 ci.yml |
| TD-011 | Pyright extraPaths 硬编码 | 2026-06-05 | 移除硬编码路径 |
| TD-012 | LLM 参数硬编码 | 2026-06-07 | LLMConfig 参数化 |
| TD-013 | 缺少 streaming 接口 | 2026-06-08 | `astream()` + 6 测试 |
| TD-015 | 缓存不支持多配置 | 2026-06-08 | 非默认 LLMConfig 不缓存 |
