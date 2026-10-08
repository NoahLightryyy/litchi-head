# 2026-10-08 分支整合

用户要求归并分支。在独立 worktree 的 codex/consolidated-20261008 操作，原目录未提交日志和其他窗口未跟踪文件均保留。

## 输入分支

- integration-project-20261001: 5f0b38a（起点）
- backend-bw021: 815f5fb
- e0-validation-checkpoint: a536081
- kr-3b-2-failure-diagnostics: 7266331
- index-multi-source: c31d956
- intraday-percent-axis: 2d4ec84
- company-research-errors: 61406fd
- screening-search: 6b8f866
- sector-map-generation: 06df022
- frontend-integration: bdc5ba5、intraday-frontend-client: 2fb2c6d、main: 374df7f 已在起点祖先中。

## 冲突决策

保留最新 K 线重试分类与诊断，旧E0实现/测试及会话恢复工具合入；旧日志另存，不覆盖最新交接。指数接三源核验并保留闭市对齐规则。分时百分比轴、行情栏、分钟量额副图同时保留，更新图表重建后的依赖。公司解读七字段和条件性股价影响保留，加入阶段错误与有界纠正；前端补丁已落入正式组件并清理中间件。选股行业搜索保留；板块已核验资料的AI解释和生成地图版本并列。

## 验证

最终 `python scripts/check.py --full` 6/6通过，Python2371 passed、7 skipped、19 deselected；前端141 passed、生产构建成功。指数21项、公司23项、地图10项、检查脚本43项专项通过；前端141项通过，生产构建通过。首次全量在2083项通过后因检查脚本测试未模拟upstream失败，已修正测试环境依赖。Turbopack不支持跨根node_modules软链接，隔离工作区使用依赖副本后构建成功。

## 边界

TD-081（东财上游）、RANKING-HISTORY-001、新闻历史覆盖与模型语义审核仍开放；合并不代表外部数据故障修复。会话恢复TD-076/077/079/080按跨部门清单保留开放。未运行付费AI生成或交易操作。


## 最终验收与整理

浏览器3068连接隔离后端8068。300893真实报价、行情栏、百分比轴和分钟量额图同时可见；三图左右轴/绘图区实测均66/546/80像素，控制台无错误。BK0499核验A+H结构、AI解释入口、新生成地图入口及209只成员正常；未触发付费生成。搜索的上游失败提示与重试入口可见，现有东财502仍未关闭。

补齐会话恢复文档入口，检查脚本与恢复规范测试通过。学习卡片同步了分支可达性与主副图轴位。旧模型语义/数据覆盖债务保留。

验收后将本地main快进至整合版本，删除5个未被worktree占用且已合并的旧本地分支：backend-bw021、e0-validation-checkpoint、frontend-integration、intraday-frontend-client、kr-3b-2-failure-diagnostics（均codex/前缀）。临时consolidated-20261008也移除，其所有提交留在main历史。

其余6个分支仍被其他工作区占用，保留分支和未提交文件；所有已提交内容均为main祖先。原Desktop目录仍在integration-project-20261001，避免切换共享脏工作区。main在本轮branch-consolidation隔离目录。此轮未修改远程分支；GitHub推送与远程清理由后续同步处理。
