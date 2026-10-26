# 产业结构代表企业补充 v1（2026-10-26）

用户批准在AI产业结构列出相关龙头/有影响力企业。使用代表企业及影响力理由，不生成无依据市占率排名。
本接口独立补充已保存草图，不要求重画、不把公司变成供货关系节点。

POST `/api/market/sector/{sector_id}/chain-companies`，sector_id沿用BKdddd或sina:new_/gn_代码。
请求 `{sector_name: string(1–80), refresh: false}`。首次在草图完成后生成，成功结果按代码、名称、
完整草图摘要、模型及资料/提示版本持久缓存。再次打开读取缓存；refresh=true为显式付费更新。
无定时或焦点付费刷新；同键单飞、全局最多2任务、120秒截止。未保存草图返回409，不代触发绘图。

200为 `ChainCompaniesResponse`，见backend/chain_companies_contract.py：
- schema_version=1，sector_code/name，graph_revision(SHA256)，graph_nodes(id/label)，generated_at/model/cached。
- companies最多12家，各有node_id/name/business/influence、a_share_code可空、reference_status、sources。
- business为业务角色；influence为AI影响力判断，不是市场份额、评级或供货事实。
- public_reference表示有可查看的业务资料，不代表影响力已独立核验。ai_candidate保留名称/研究判断，明确资料待补。
- sources为程序附加的实际资料或已收录官方页面（title/url/excerpt/accessed_at）；不得让模型编造URL。
- A股代码必须经同名身份资料核对才能链接本站股票页；未知、港美股等仅展示名称及已有原文链接，不套A股路由。
  缓存读取再次校验代码对应的公司资料网址和名称摘要，避免损坏缓存指向另一只股票。
- 草图环节/企业身份必须匹配，不能重复同一家企业或引用不存在的节点。
- 所有影响力判断标记ai_unreviewed；非每个节点都必须凑公司，跨行业概念按类别组织。

错误结构 `{error:{code,message,retryable}}`：409 NOT_READY、429 BUSY、504 TIMEOUT、502 FAILED、503 STORAGE。
除409为false，其余允许用户手动重试。前端不对模型失败自动重跑；更新失败保留旧清单和时间，
公司补充失败不隐藏原结构。错误信息只在本区域显示，不扩大成全站不可用。
首次读取的网络失败重试仍使用refresh=false，以复用可能已完成的结果；仅损坏缓存修复或用户更新使用refresh=true。
