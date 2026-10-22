# 69 能复用代码，不代表能复用结论

一句话：把每项能力拆成“数据、语义、运行、展示”四层，才知道该复用什么、补齐什么。

## 项目实例

`backend/etf_contract.py`有身份和报价，但没有指数/持仓，所以可以复用报价卡，不能声称已知ETF政策暴露。`frontend/lib/portfolio.ts`有手填市值，却无现金和可卖数量，所以能复用录入交互，不能推出完整账户可买量。

`backend/company_research.py::validate_citations`证明引用ID存在，不证明材料支持观点；`src/utils/cost_tracker.py`记录估算费用，不等于调用前预算限制器。这些边界进入[能力盘点](../02-requirements/differentiation/CAPABILITY_INVENTORY.md)。

## 自己试试（3–5分钟）

打开EtfDetail，找出报价时间，再搜索持仓权重字段；对照能力盘点R10/N04，说明两者为什么不是同一项能力。然后查看交易bridge与quantity_pct定义，解释为什么必须先冻结语义，再复用计算代码。

多人并行先约定基线和拥有路径：只读盘点可共目录，写代码必须独立worktree；接口冻结前只做证据样例与草案。人日估算也不能直接当多窗口后的日历工期。

上一张：[68 AI草图与证据边界](68-inferred-graph-evidence-boundary.md) · [索引](README.md)
