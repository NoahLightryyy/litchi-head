# 71｜持久研究任务与可信计算边界

一句话：把“用户点了一次”保存成幂等任务，把“可以算出数字”和“有足够证据展示数字”分开。

## 项目里的实现

`backend/policy_research.py`先在SQLite登记请求与精确指纹，同键异内容返回冲突，同键同内容只读原任务。研究有预算预留、超时、终态以及重启中断处理。刷新或离开页面不能意味着重新付费；`frontend/lib/policy-capital.ts`的canSubmitResearch在恢复原记录前、状态未知或运行中禁止新建。

`backend/capital_preview.py`使用Decimal和二分查找最大可负担数量，按最低量加整数步长递增。实际ready必须同时有服务端核验的标的、规则、费用、现金、权限及时点。客户端把includes_all_applicable_costs填true并不构成核验。

原文快照哈希核验防止本地材料变化；引用ID存在性检查只防悬空引用。supported事实还要匹配核验文本、评估与引用集合；新增AI推断仍可能有逻辑错误，不能宣称已证明投资收益。

## 自己试试（约5分钟）

运行 `.venv/bin/pytest tests/test_capital_preview_runtime.py tests/test_policy_capital_integration.py -q`。查看同一幂等键反复POST只调用一次mock模型的用例；再把请求中的费用改动，观察与服务端核验不一致导致blocked，金额全部为空。

前卡：[70 证据时间与缺项阻断](70-evidence-dates-and-blocked-execution.md)。后续关注：实际券商费用证明接入与真实模型保留样本验收。

原始响应归档用目录内.gitattributes禁用换行规范化；否则Windows检出时CRLF/LF变化会破坏SHA-256。原文空白属于证据字节，不按代码格式化。

## 集成时检查实际页面消费者

组件和API分别提交不等于用户可用。2026-10-22集成发现ResearchContext缺少页面引用，已在股票与板块页面挂接；板块行情失败时仍可独立展示证据。验证应同时覆盖实际app路由、页面入口和缺项阻断，不能仅检查组件单测。
