# 70｜证据时间与缺项阻断

一句话：资料存在不等于资料当前有效，输入不齐就不要输出精确数量。

本项目 `backend/policy_capital_contract.py` 将持仓报告期与披露日期分开，保留净值权重和披露覆盖范围；2026Q1的中微4.29%不能当今天的完整ETF敞口。政策成文日也不能代替生效日。

ExecutionPreview在blocked时强制数量、费用、余额都为空；ResearchJob要求终态负载一致。Pydantic验证结构，不能替代原文核验与服务端引用、身份校验。

自己试试：运行 `pytest tests/test_backend/test_policy_capital_contract.py -q`，把历史持仓日期改为披露之后，或给blocked填200股，观察验证失败。约3分钟。

前卡：[69 能力盘点](69-capability-inventory-before-integration.md)。后续：生产HTTP消费者测试与规则计算边界。
