# 2026-10-22 分支归并与申请展示主线集成

## 范围与隔离

用户要求管理并合并分支。fetch后确认远端main=e99c49d，已含10月8日指数、分时图、公司解读、筛选、产业地图、E0和会话恢复批次。本次在独立readme-graduate-application工作区合入main，保留10月18日契约、政策研究、本金预览及10月22日README。原Desktop工作区的未提交文件未整体复制、未暂存、未变基。

政策06fefcd、本金b64e0a5、前端10c4ee9相对5a4ec25的18个文件逐字节核对，已全部包含于集成版本；后续以无内容变更的正常merge保留其祖先关系。其他旧分支通过merge-base核对已在主线中。

## 冲突与修复

README采用本次中英文工程展示结构，补回主线三源指数、百分比图、地图、筛选、E0及Git校验的会话恢复入口。债务与日志索引保留两侧记录。backend/main.py自动合并后核对同时注册产业地图与政策/本金API，保留生命周期恢复。

发现已提交ResearchContext没有页面消费者；原目录的页面挂接尚未提交。只迁入股票、东财板块（含失败态）、新浪板块的组件挂接，保留主线GeneratedMap，未带入尚未提交的ETF页面和AI草图方案。

首次全量2162 passed后，README会话恢复入口回归断言失败；补回真实文档入口，未削弱测试。源分支带来的历史Markdown空白告警不改写历史文件；对最终相对main差异执行diff --check。

## 验证

全量Python 2427 passed、7 skipped、19 deselected；前端150/150、健康模块覆盖率门禁通过；生产构建通过。Ruff与src/backend Pyright通过，README本地链接检查通过。本次不运行付费AI或交易操作。隔离浏览器3072/后端8072：688012页面历史政策与公司证据、事实/推断区分可见；空账户数据选择上海后预览明确blocked，全部缺项列出，无精确数量。BK0917页面政策证据、不可交易提示与主线GeneratedMap并存。真实报价可达、分钟数据失败保留诊断，未用假数据补齐。

## 债务与学习

DOC-INTEGRATION-20261022记录组件缺少页面挂接并当次修复；开放数不变。已有卡71补充集成边界。既有上游可靠性、费用/权限证明、真实模型评估债务不关闭。

## 分支处置

目标为检查通过后发布main，清理已在main中的旧远端主题分支；被其他worktree占用的本地分支保留。源Desktop目录仍是旧集成分支且有未提交工作，不在其上切换/合并。未提交ETF、草图和实验材料不等于本次已发布。


## 发布与清理结果

集成树464e1a8经三个无内容变更的来源merge后为fc1bc00；diff确认树内容未变化。本地全量闸门最终6/6。GitHub连接器创建PR返回403（integration权限不足），按用户合并授权以普通快进push将远端main由e99c49d更新至fc1bc00，没有force。

已删除5个祖先已在main中的旧远端分支：backend-bw021、e0-validation-checkpoint、frontend-integration、intraday-frontend-client、kr-3b-2-failure-diagnostics（均codex/前缀）。清理2个已不存在工作区的注册记录，并用branch -d删除已合并的company-research-errors、screening-search本地分支；其提交仍可从main追溯。其他在用worktree与源目录未提交内容保留。

GitHub CI已启动（run 39768656527）；首次查询Python3.12/3.13与前端均运行中。顺带确认此前main的10月8日CI曾在Pytest失败，不能将历史本地通过写成远端全绿。最终CI结果由会话收尾核对；后续纯日志提交也会触发CI。
