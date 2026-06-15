# ADR-004: Streamlit 作为 MVP 前端框架

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-03 |
| **状态** | ✅ 已采纳（Phase 1 有效） |
| **影响范围** | frontend/ |

**上下文**：
需要在前端展示辩论结果、账户信息，但前端开发资源有限。

**决策**：
Phase 1 使用 Streamlit 搭建 MVP 前端，Phase 2 再迁移到 React/Next.js。

**理由**：
1. 纯 Python，无需前端团队
2. 最快速度出可交互原型
3. `st.cache_data` 天然适配数据缓存场景
4. 部署简单（单服务器 + `streamlit run`）

**舍弃方案**：
| 方案 | 舍弃理由 |
|------|---------|
| React + Next.js | 学习成本高，Phase 0/1 资源不足 |
| Gradio | 更灵活但金融风格 UI 定制不如 Streamlit + Plotly |

**后果**：
- ✅ 非前端开发者也能快速搭界面
- ⚠️ Phase 2 重构为 React 时前端要重写（已知债务）
