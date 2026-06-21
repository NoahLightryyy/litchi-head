---
department: 后端 API 部
codebase: backend/
last_updated: 2026-06-21
---

# 🌐 后端 API 部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| market 路由（5 endpoint） | ✅ | 指数/板块排行/板块详情/brief/4 端点 |
| stocks 路由（5 endpoint） | ✅ | 搜索/行情/K 线/新闻/资金流向 |
| debate 路由（3 endpoint） | ✅ | 辩论触发/状态/结果 |
| trust 路由（2 endpoint） | ✅ | 信任度报告/排行榜 |
| 技术指标（indicators.py） | ✅ | MA/RSI/MACD/布林带纯 Python |
| 异步超时控制（async_utils.py） | ✅ | `run_sync()` 15s 超时封装 |
| 健康监控（/api/health） | ✅ | 实时数据源健康暴露 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| test_market.py（6 端点 + 5 辅助函数） | 52 |
| test_stocks.py（6 端点） | 15 |
| test_debate.py（3 端点 + session 生命周期） | 9 |
| test_trust.py（2 端点 + 映射逻辑） | 11 |
| test_indicators.py（技术指标 100% 覆盖） | 43 |
| **backend 合计** | **77** |

### 关键架构决策

- **严格 HTTP 语义**：200 正常 / 404 无数据 / 422 验证失败 / 500 系统错误 / 503 数据源不可用
- **异步桥接**：所有同步数据采集调用通过 `run_sync(timeout=15)` 封装
- **CORS 环境变量化**：从 `BACKEND_CORS_ORIGINS` 读取，硬编码默认值仅用于开发

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-039 | debate/run 无 API 速率限制（被刷 = LLM 费用起飞） | 🟡 | 1h |
| TD-054 | CORS 地址硬编码（需改环境变量） | 🟢 | 10min |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-020 | 板块数据增强层缺失 | 2026-06-17 |
| TD-023 | 全返回 200 状态码 | 2026-06-17 |
| TD-024 | 数据源调用无超时 | 2026-06-17 |
| TD-036 | 路由测试全覆盖 | 2026-06-18 |

---

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | TD-039 API 速率限制 — slowapi + debate/run 特别限流 | 无 |
| 2 🟢 | TD-054 CORS 改环境变量 | 无 |

---

## 关键文件索引

| 文件 | 说明 |
|:-----|:------|
| `backend/main.py` | FastAPI 应用入口 + CORS 配置 |
| `backend/routers/market.py` | 指数/板块/产业链路由 |
| `backend/routers/stocks.py` | 搜索/行情/K 线/新闻/资金流向路由 |
| `backend/routers/debate.py` | 辩论触发/状态/结果路由 |
| `backend/routers/trust.py` | 信任度报告/排行榜路由 |
| `backend/indicators.py` | 纯 Python 技术指标计算 |
| `backend/async_utils.py` | 同步→异步超时桥接 |
| `backend/config.py` | 后端环境变量配置 |
| `tests/test_backend/` | 77 测试覆盖 17 端点 |
| `docs/06-departments/08-backend-api/ROLE.md` | 👤 后端 API 部角色定义 |
| `docs/06-departments/08-backend-api/STANDARDS.md` | 📐 后端 API 部技术规范 |
