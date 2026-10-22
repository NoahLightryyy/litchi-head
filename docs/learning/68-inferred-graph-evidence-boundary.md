# 68 让AI补图，而不把推断变成证据

一句话：缺资料不必停止研究，但AI草图与已核验关系必须拥有不同契约。

## 本项目实现

`backend/chain_draft_contract.py`限制2–8节点、1–12边，拒绝悬空边、自环和重复；`backend/routers/chain_draft.py`经过统一LLM服务生成，按代码/名称/模型/提示版本隔离缓存，原子保存后返回。`frontend/lib/chain-draft.ts`二次检查身份与结构。`chain-draft-map.tsx`用虚线和AI推断标签展示；原 `ChainEvidenceMap` 的来源规则保持不变。

结构正确只能证明图可渲染，不能证明产业事实真实。材料、设计、制造的通用知识可以用来建立核验清单，不能直接变成某家公司与另一家公司有供货合同。

## 自己试试（3分钟）

运行 `.venv/bin/pytest -q tests/test_backend/test_chain_draft.py`，检查悬空边和失败不缓存。打开BK0917，展开“需要核验什么”，刷新后看生成时间是否不变及“已保存草图”。修改测试目标代码，消费者应拒绝错配图。

上一张：[67 结构化答案一致性](67-structured-answer-consistency.md) · [索引](README.md)

## 失败缓存不能阻止自动生成

`staleTime: Infinity`用于复用成功图；同时设置`refetchOnMount:false`会使失败查询回到页面也不再执行。`frontend/lib/chain-draft-query.ts`恢复挂载与联网触发，并按错误分类设置有限重试。QueryObserver回归测试覆盖失败返回、成功不重复、繁忙恢复与离线恢复。

## 2026-10-22 与资料地图合并

`frontend/app/sector/[id]/page.tsx`同时保留资料驱动GeneratedMap与缺图ChainExplorer草图；后者显式标记未经来源核验。合并同一区域的功能不能直接择一覆盖，需要检查各自证据语义、缓存和触发方式。浏览器使用隔离模型测试桩验证接入，不把测试输出写入正式数据或当成模型质量证据。
