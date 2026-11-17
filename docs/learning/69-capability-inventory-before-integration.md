# 69 能复用代码，不代表能复用结论

一句话：把每项能力拆成“数据、语义、运行、展示”四层，才知道该复用什么、补齐什么。

## 项目实例

`backend/etf_contract.py`现在有身份、报价和独立RAW日线，但没有实际指数成分及持仓，所以可以展示行情，不能声称已知ETF政策暴露。`frontend/lib/portfolio.ts`有手填市值，却无现金和可卖数量，所以能复用录入交互，不能推出完整账户可买量。

`backend/company_research.py::validate_citations`证明引用ID存在，不证明材料支持观点；`src/utils/cost_tracker.py`记录估算费用，不等于调用前预算限制器。这些边界进入[能力盘点](../02-requirements/differentiation/CAPABILITY_INVENTORY.md)。

## ETF可以共用辩论图，但要换掉公司资料和错误假设

不能把ETF代码直接传给股票采集器，再把营收、ROE和管理层分析的空结果交给模型补全。
也不能因为基金持仓尚未接入，就挡住已有报价、价格历史和政策资料的研究。

本轮的分工是：`backend/etf_research.py::collect_etf_research` 独立并行采集基金身份、
场内报价、日线及相关资料，某一项失败时保留其他项；`InstrumentResearchContext`
带着身份、资料与缺口进入现有 `DebateOrchestrator`。`src/debate/etf_analysts.py`
保留分析师标识和顺序，把公司基本面角色换成基金结构与主题角色，其余角色补充ETF研究范围。
这样复用的是已有辩论图、状态传递与会话能力，不是上市公司结论。

`instrument_type=etf` 也进入运行请求及会话身份，避免“同一个六位代码”自动意味着
同一种分析对象。政策文章的主题命中仍只是线索：实际持仓及权重、NAV、折溢价、
跟踪指数、规模、申赎、费率和跟踪误差未提供时保持未知。未复权价格变化不能直接当总回报，
没有计算的MA/RSI/MACD不能写成已有数值；这些限制随资料进入分析，不靠模型记忆补造。

实现边界和交付边界也应分开：本轮已验收前端ETF入口、图表与历史恢复。单次实网完成
5分析员、3位大师及交叉/独立审阅，另2位超时；还发现量价描述矛盾，因此链路可用不代表
AI内容完全正确。确定性涨跌/量比摘要减少读数错误，语义核验仍是开放质量工作。`etf_daily_facts`先用Decimal计算，0.792→0.749为-5.43%，
516826000份/847322400份为0.61；比较日与样本覆盖一同传入模型，避免让它重新猜算。

## 自己试试（3–5分钟）

打开EtfDetail与EtfKlineDisplay，找出报价时间和最后日线日期，再搜索持仓权重字段；说明两者为什么不是同一项能力。运行 `python -m pytest tests/test_backend/test_etf_research.py tests/test_debate/test_etf_graph.py -q`，查看资料缺项保留和ETF走现有图的测试，不启动付费模型。然后查看交易bridge与quantity_pct定义，解释为什么必须先冻结语义，再复用计算代码。

多人并行先约定基线和拥有路径：只读盘点可共目录，写代码必须独立worktree；接口冻结前只做证据样例与草案。人日估算也不能直接当多窗口后的日历工期。

上一张：[68 AI草图与证据边界](68-inferred-graph-evidence-boundary.md) · [索引](README.md)
