# 78 · 没有生成分析，不等于没有投资共识

一句话：先判断任务是否成功，再解释观点是否一致；HTTP错误不是投资信号。

## 项目真实代码

- `src/utils/llm.py`：请求失败与Pydantic解析失败分开；明确余额不足不自动重试，也不送入付费格式纠正。
- `backend/routers/debate.py`：至少一个成功流派才算有可读研究；空/全失败保存failed和诊断，不生成复盘。
- `src/debate/orchestrator.py`：全失败不保存为中性决策记忆。
- `frontend/lib/debate-failure.ts`及`components/stock/debate-panel.tsx`：根据旧记录success/error安全归类，原始错误不直接展示，不修改历史研究。

## 三件不同的事

1. **模型没答出来**：网络、账户或格式错误；说明技术原因。
2. **模型认为证据不足**：有效返回了分析，但方向尚无法支持；展示缺少哪些依据。
3. **观点存在分歧**：都有可用观点，但方向不同；展示争议。

HTTP200只证明接口正常返回，completed应代表业务确实产出结果。不能把失败占位Neutral/0分当市场看法，也不能因为一部分失败就删除其他已经生成的研究。

## 自己试试（5分钟）

1. 用离线测试模拟Insufficient Balance，确认一次请求后报错，不去真实请求模型。
2. 将五个analyses都设success=false，确认503且无复盘；留一项成功则可查看部分研究。
3. 打开旧completed失败fixture，确认余额提示出现而方向图/计划入口消失；将错误改为未知，不能仍声称余额不足。

前一张：[ETF关键词搜索](77-etf-keyword-identity-search.md) · 相关：[统一LLM层](03-llm-unified-layer.md) · [索引](README.md)


测试补充：mock LLM不等于完全离线。`tests/test_risk_r1_three_layer.py`的运行测试还需要显式注入DataCollector；只验证图结构时不需要真实采集。避免用开发机保存的账户与实时数据证明单元测试通过。
