# 🔍 数据源深度审计报告

> 调研日期：2026-06-16 | 调研范围：akshare 稳定性 + 竞品对比 + 国内量化平台 + Bloomberg/TradingView/eToro/Yahoo Finance
> 调研方法：30+ 网络搜索，7 组独立子代理并行调研

---

## 1. 当前数据链：akshare

### 技术本质

**akshare 不是 API，是一个 HTTP 爬虫库。** 每次数据调用都在做：
1. 逆向东方财富前端 API 参数，构造抓取 URL
2. 伪造 HTTP Header（User-Agent / Referer / Cookie）
3. 发送 HTTP GET 请求到东方财富服务器
4. 解析 HTML/JSON 返回为 pandas DataFrame

**数据流**：
```
交易所 → 东方财富服务器（1-5 秒页面刷新延迟）
              ↓ HTTP 爬虫（DNS+TLS+请求 0.5-2 秒）
         DataCollector（30s TTL 缓存）
              ↓
         FastAPI 桥接层 → 前端
```

### 实测性能（2026 年 30 天连续压力测试）

| 指标 | **akshare** | 行业标杆 Tushare Pro |
|:-----|:----------:|:------------------:|
| **API 调用成功率** | **92.1%** | 99.7% |
| **实时行情延迟** | **3-5 分钟** ⚠️ | 1-3 秒 |
| **平均响应时间** | **850ms** | 180-320ms |
| **数据一致性** | **96.8%** | 99.9% |
| **服务可用性** | **95.3%** | 99.9% |
| **异常恢复时间** | **5-10 分钟** | <1 分钟 |

### 已知问题

| 问题 | 典型表现 | 社区报告 |
|:-----|:---------|:--------|
| 东方财富改版必断 | CSS 类名/API 结构变化，解析立即挂 | 每年数次 |
| 复权价格 bug | 单日出现 90% 涨幅（东方财富算法错误） | GitHub #3913 |
| 大盘股返回空 | 5000+ 股票只有前 600 只返回数据 | GitHub #5887/#6100 |
| IP 封禁 | 10 秒内 2 次请求即封 | GitHub #6030 |
| 版本升级炸兼容 | 升到 v1.16.35 挂了，降回 v1.15.94 正常 | GitHub #5820 |

---

## 2. 竞品怎么做

### 数据源层次对比

| 层次 | 年费 | 代表产品 | API 成功率 | 延迟 |
|:-----|:---:|:--------|:---------:|:----:|
| **机构级** | 1-20 万+ | Bloomberg/万得(Wind)/Choice/Refinitiv | 99.99% | 微秒-毫秒 |
| **专业 API** | 500-5000 | Tushare Pro/JQData/Polygon.io | **99.7%** | 180-320ms |
| **免费开源** | 0 | **akshare ★ 我们**/BaoStock/yfinance | **92.1%** | 850ms-5min |

### 竞品保障数据质量的手段

#### ① 多源交叉校验（最关键）

| 平台 | 数据源数 | 供应商 |
|:-----|:-------:|:-------|
| **米筐 RiceQuant** | **5 家** | 恒生聚源 + Wind + 巨灵等 |
| **聚宽 JoinQuant** | ≥3 | 自采 + Tushare + 部分 Wind |
| **eToro** | 4 条独立管道 | Nasdaq Basic + 交易所直连 + Crypto + Grok |
| **Bloomberg** | 330+ 交易所 + 5000+ 报价商 | 多源 → BGN 共识价格 |

**核心模式**：同一字段（收盘价）从 3-5 个数据源获取 → 交叉对比 → 差异自动标记。

#### ② 数据清洗工厂

聚宽和米筐都有自建系统：

- **复权处理引擎**：自动计算前/后复权，分红不产生"价格断崖"
- **异常值过滤**：3 倍标准差法，捕获负数价格/成交量暴增
- **PIT（Point-in-Time）机制**：确保时间对齐，**避免未来函数**
- **财务数据对齐**：年报/季报对齐到实际发布时间

#### ③ 直接交易所授权

| 平台 | 授权级别 |
|:-----|:---------|
| **同花顺** | 上交所首批 Level-2 授权（2006 年），直连交易所机房 |
| **东方财富** | 上交所 Level-2 授权（2008 年） |
| **通联数据（优矿 UQER 母公司）** | 沪深交易所首批授权转发机构 |
| **Bloomberg** | 330+ 交易所直连 |

**授权费用**：上交所 Level-2 约 35 万元/年固定 + 每终端每月 30 元浮动。

#### ④ AI 特有的幻觉防御

```python
第 1 层：结构化数据源（价格/K线/财务）→ 走 API，不走 LLM
第 2 层：RAG 实时检索（新闻/公告）→ LLM 只做摘要，不编造
第 3 层：人机回路（交易决策）→ AI 建议，人确认
```

eToro UK MD 原话：*"General LLMs are not reliable stock pickers — they misquote figures, lean too hard on pre-established narratives, and overly rely on past price action."*

---

## 3. 对我们的影响

### 当前差距

| 维度 | 行业标准（聚宽/米筐） | 我们 |
|:-----|:------------------|:----|
| 数据源数量 | 3-5 个 | **1 个**（akshare） |
| 数据清洗工厂 | 有 | **无** |
| 交叉校验 | 跨源秒级比对 | **无** |
| 异常检测 | 3σ 自动告警 | **不做**（"尽力而为"返回空列表） |
| 复权准确性 | 自研引擎校验 | **依赖东方财富**（已有 bug 报告） |
| 实时行情延迟 | 1-3 秒 | **3-5 分钟** |
| 服务可用性 | 99.9% | **92.1%** |

### 结论

> **akshare 适合 MVP 原型验证，不适合生产环境。**
> 当前架构没有数据出错保护——挂了就是空了，错了就是错了。

---

## 4. 推荐架构演进路径

### Phase 1（现在，不花钱）

✅ 已做：

- ~~`DataCollector` 加失败率监控（`/api/health/data-source` 实时可查）~~
- ~~踩数据源造假红线并全面清除~~

❌ 待做：

- 锁定 akshare 版本不升级
- 持续运行健康监控，累积 1 个月真实失败率数据

### Phase 2（下一两周，零成本）

> **修正**：原方案推荐 Tushare Pro（500 元/年），但面向散户群体必须零成本。
> 改用 **adata + zzshare + efinance** 三源组合，全部免费。

**adata**（主数据源）：
- 5 源融合：同花顺 + 东方财富 + 新浪 + 腾讯 + 百度，源挂了自动切另一个
- 覆盖：日/周/月 K 线、实时 5 档行情、概念板块、资金流向、北向资金、龙虎榜
- Apache-2.0 开源，3300+ Star，v2.9.0（2025 年 4 月发布）

```python
import adata

# 多源自动切换，上层无感知
df = adata.stock.market.get_market(
    stock_code='000001', k_type=1,
    start_date='2025-01-01'
)
```

**zzshare**（Tushare 兼容备源）：
- 接口规范与 Tushare Pro 一致，无需 Token、无需积分、完全免费
- 40+ 接口（日线、资金流向、板块热度、龙虎榜、情绪指标）
- 若将来切 Tushare Pro，代码一行不用改

```python
from zzshare import pro
df = pro.daily(ts_code='600519.SH', start_date='20250101', end_date='20250616')
```

**efinance**（资金流向专项补充）：
- 主力/大单/超大单资金流向分层更细致

**数据层 Provider 抽象**（无论选什么数据源，架构必须抽接口）：

```python
class DataSource(Protocol):
    def get_all_stocks(self) -> list[StockInfo]: ...
    def get_realtime_quotes(self) -> list[StockQuote]: ...

class AKShareSource(DataSource): ...   # Phase 1 现有实现
class ADataSource(DataSource): ...     # Phase 2 新接入（主源）
class ZzshareSource(DataSource): ...   # Phase 2 新接入（备源）
class FallbackSource(DataSource): ...  # 主源挂了切备用
```

### Phase 3（产品化）

- **BaoStock** 作为历史回测数据源（1990 年起全 A 股免费）
- **Pytdx 通达信直连** 作为超低延迟实时行情
- 本地 SQLite/Parquet 持久化缓存，减少实时调用
- 多源校验引擎：同一字段多数据源对比，不一致时标记

---

## 5. 数据原则

### 原则一：数据源不造假

无论用什么数据源，都遵守以下规则：
- 空就是空，显示"暂无数据"
- 未实现的功能显示"待实现"
- 绝不硬编码填充数据冒充功能

### 原则二：数据源不唯一

任何生产系统不能只依赖一个数据源：
- 主源（Tushare Pro / 付费 API）
- 备用（akshare / 免费降级）
- 历史（BaoStock / 本地缓存）

### 原则三：数据质量可观测

必须有实时监控：
- 每个 endpoint 的调用次数/失败率/延迟（已实现，`/api/health/data-source`）
- 失败时自动告警
- 累积长期数据驱动决策（"akshare 到底多差"由数据说话）

---

## 6. 调研来源

| 调研主题 | 来源 |
|:---------|:-----|
| akshare 稳定性 | GitHub Issues #3913/#5887/#6030/#6100, CSDN, GitCode |
| Tushare vs AKShare vs BaoStock | TradingAgents 30 天实测数据, GitCode 对比 |
| 聚宽/米筐/优矿 | JoinQuant 官方文档, RiceQuant SDK 文档, DataYes 授权公告 |
| 同花顺/东方财富 | 上交所/上期所授权名单, 2022 年 11 月集体宕机事件报道 |
| Bloomberg | 官方技术博客, SEC 罚款记录, A-Team 7 年最佳奖 |
| TradingView | AWS 案例研究, Broker Integration 文档, CQG 合作 |
| eToro Tori AI | 纳斯达克合作新闻稿, xAI Grok 集成, IJAM 论文 |
| Yahoo/Google Finance | 官方数据提供商清单 (SLN2310), yfinance Issues |

---

> **最后更新**：2026-06-16 | **责任人**：AI + 项目维护者定期审视
