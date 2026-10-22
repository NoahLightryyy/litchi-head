# 67 解释正确，不代表结构化答案正确

一句话：让程序消费模型答案前，要单独核验类型、计算和证据边界。

## 项目中的真实案例

`scripts/evaluate_research_smoke.py` 的费用题要求输出220元。模型reason正确计算100+120=220，answer却写180。最低买入题reason说3000超过2000，answer却写true。`score`严格评分，没有从理由补救机器字段；完整输出见 `docs/02-requirements/differentiation/evidence/research-smoke-20261018T160521Z/results.jsonl`。

复核在这6题修正错误，但增加调用预算，不能据此证明普遍收益。`frontend/lib/capital-scenarios.ts` 对同样费用使用确定性公式和分单位舍入；展示不是LLM输出。数值边界与空输入也必须先验证。

## 自己试试（3分钟）

运行 `.venv/bin/pytest -q tests/test_scripts/test_research_smoke.py`，观察“答案180、理由220”被拒绝。打开任一股票/ETF/板块详情的“政策与本金对照”，展开本金试算，把每月研究费120改成30，1万元场景成本应从220变为130；清空输入后表格隐藏。这个练习不调用付费API。

上一张：[66 四层行情进入LLM](66-four-layer-evidence-to-llm.md) · [索引](README.md)

## 嵌入详情不等于建立事实关联

`frontend/components/research/research-context.tsx`按资产类型提示需要的证据，代码和名称只绑定当前研究对象。没有政策映射时明确显示未关联，不按名称自动认定受益。试算按标的key重建，防止切换标的后误用上一页输入；旧地址复用组件，避免维护两套政策和金额口径。
