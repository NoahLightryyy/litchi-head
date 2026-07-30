# ⛁ 数据采集模块

> 多数据源行情/新闻/财务数据的获取、缓存、标准化。

## 当前状态

- ✅ Provider 抽象层设计完成
- ✅ akshare 封装可用
- ✅ 缓存层（TTL）就绪
- ✅ 统一多源证据契约、来源注册中心与独立上游完整性评估
- ✅ 首个权威来源：CNINFO 直连有数据、真实空、失败三态门禁通过；AKShare 保留为可替换适配器
- ✅ CNINFO 上市公司法定披露 PDF 停复牌事件层：明确生效日、附件 URL、原文哈希；
  不把单次公告查询冒充完整状态覆盖
- ✅ 连续证券状态账本：生命周期 + 检查点 + 连续批次；重复公告幂等，断档和冲突
  失败关闭，保留未生效转换
- ✅ 沪深官方生命周期与检查点生成：交易所原始清单哈希、CNINFO 完整批次哈希，
  确定性检查点不读取目标日之后结束的批次
- ✅ 北交所官方生命周期与停复牌状态：完整上市清单、新旧代码映射、市场日历
  分页/分类计数/窗口校验；0600/0700 进入既有账本，9001 只作盘中事件
- ✅ KR-1B-3A 审计存储：SQLite 不可变清单 + 内容寻址 Parquet 保存逐源 RAW、
  诊断与权威版本引用；篡改失败关闭并支持确定性 `as_of` 回放
- ✅ `DataEvidenceService` 并发汇总多个通道，输出统一证据信封
- ✅ 新闻与实时行情已接入正式辩论零 LLM 失败关闭
- ✅ L1 分时一期完成，动态分钟显式标记 `PROVISIONAL`
- ⟳ 下一步只做 KR-1B-3B 真实新浪/腾讯长窗覆盖证明和运行时接入；不得重建
  3A 存储或擅自更换数据源
- ⟳ 旧 Provider 继续逐个迁移到显式六态结果

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
- `src/data/evidence_service.py`
- `src/data/models.py`
- `src/data/cache.py`
- `src/data/providers/cninfo.py`
- `src/data/providers/cninfo_status.py`
- `src/data/providers/bse_status.py`
- `src/data/kline_status.py`
- `src/data/kline_store.py`
