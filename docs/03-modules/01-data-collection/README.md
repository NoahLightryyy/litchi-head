# ⛁ 数据采集模块

> 多数据源行情/新闻/财务数据的获取、缓存、标准化。

## 当前状态

- ✅ Provider 抽象层设计完成
- ✅ akshare 封装可用
- ✅ 缓存层（TTL）就绪
- ⬜ Provider 接口实现（OpenBB 模式移植）

## 文档

| 文件 | 说明 |
|:-----|:-----|
| [SPEC.md](SPEC.md) | 规格说明书（含战线格局 + 架构对照） |
| [ADR.md](ADR.md) | 架构决策（ADR-003 akshare 数据源选型） |
| `../../05-decisions/ADR-001-pydantic.md` | Pydantic 数据契约（跨模块引用） |

## 对应源码

- `src/data/collector.py`
- `src/data/models.py`
- `src/data/cache.py`
