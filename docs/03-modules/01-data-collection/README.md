# ⛁ 数据采集模块

> 多数据源行情/新闻/财务数据的获取、缓存、标准化。

## 当前状态

- ✅ Provider 抽象层设计完成
- ✅ akshare 封装可用
- ✅ 缓存层（TTL）就绪
- ✅ 统一多源证据契约、来源注册中心与独立上游完整性评估
- ✅ 首个权威来源：CNINFO 直连有数据、真实空、失败三态门禁通过；AKShare 保留为可替换适配器
- ⟳ 旧 Provider 正在逐个迁移到显式六态结果；尚未接入正式辩论链

## 文档

| 文件 | 说明 |
|:-----|:-----|
| [SPEC.md](SPEC.md) | 模块规格（职责边界、代码结构、数据模型） |
| [RESEARCH.md](RESEARCH.md) | 调研分析（战线格局、竞品对比、研究问题） |
| [ADR.md](ADR.md) | 架构决策（ADR-003 akshare 数据源选型） |
| `../../05-decisions/ADR-001-pydantic.md` | Pydantic 数据契约（跨模块引用） |

## 对应源码

- `src/data/collector.py`
- `src/data/evidence.py`
- `src/data/models.py`
- `src/data/cache.py`
- `src/data/providers/cninfo.py`
