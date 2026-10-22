# 缺图时的AI结构草图契约 v1

2026-10-18 用户授权缺图时绘制。与核验目录及chain-analysis完全分离，不改变旧接口。

POST `/api/market/sector/{sector_id}/chain-draft`，代码允许BKdddd或sina:原生代码，请求体sector_name（1–80字符）。首次生成调用既有DeepSeek统一服务；同代码/名称/模型/版本缓存命中不调用。前端缺图时自动请求一次，无后台批量生成、采用有限次自动恢复。相同任务单飞，全局最多2任务；超时90秒。

200直接返回DraftResponse，严格模型见backend/chain_draft_contract.py：schema_version=1、sector_code/name、graph（map_kind、scope、nodes、edges）、generated_at、model（请求模型）、cached、review_status固定ai_inferred_unverified。节点id/label/role/verify；边source/target/explanation；2–8节点、1–12边，拒绝重复及悬空边、自环。全部节点与边都是模型推断，没有核验来源；不能进入ChainEvidenceMap或计算引用覆盖率。禁止具体公司供货、股票代码、伪造引文及行情建议。概念分类绘制concept_structure，不能强行编造上下游。

错误沿用error:{code,message,retryable}。429 CHAIN_DRAFT_BUSY、504 CHAIN_DRAFT_TIMEOUT、502 CHAIN_DRAFT_FAILED均可手动重试；422参数错误不可原样重试。持久化失败返回503 CHAIN_DRAFT_STORAGE，不能声称已保存。错误显示在地图区域，不影响行情。缓存本地原子写，模型/提示版本变化隔离；生成时间始终显示，不冒充最新行业事实。再次POST只读有效缓存，无定期付费刷新。

2026-10-18恢复逻辑修正：首次缺图自动请求；失败后返回页面或恢复联网重新获取，成功结果保持新鲜且不重复生成。繁忙最多6次自动重试，网络/429最多2次，模型失败/超时最多1次；间隔5至15秒。参数、缓存存储及消费者结构错误不在当前页面自动重试。次数耗尽显示错误与手动重试，不永久锁死失败缓存。
