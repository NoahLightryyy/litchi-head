# 2026-11-04 辩论调用失败不再冒充条件不足

## 事实与根因

- 恢复codex/market-availability，起点4756ee4；Git、session_state MATCH、交接及最新日志一致；已有node_modules软链接不暂存。
- 用户588110记录deb_3b829df108cd于2026-11-04 23:03北京时间结束，5位大师均返回HTTP402 / Insufficient Balance。早期2份分析师报告成功，随后模型余额失败；行情源请求成功。这不是单源门槛或ETF证据不足。
- 原LLM层把HTTP异常统一包装成结构化解析错误；run路由无论有效分析数都保存completed；前端将失败流派归入条件缺失，0/5仍展示三周期分布和计划入口。

## 修复

- 模型明确余额错误规范为LLM_INSUFFICIENT_BALANCE；其他HTTP错误保留安全状态码，调用失败不进入解析纠正逻辑。余额错误不自动重试。
- 后端契约先提交9cfb287：全部失败/空结果返回503 ANALYSIS_BALANCE_INSUFFICIENT或ANALYSIS_FAILED，retryable=false、session_id；持久化failed且保留诊断。不自动创建复盘或决策记忆；部分成功仍保留真实返回研究。
- 旧completed失败记录按已有success/error只读分类，不迁移/改写原文评分：主提示明确具体原因，不显示方向统计或入场计划；各流派失败详情折叠，不向普通用户吐原始HTTP正文。
- 真实证据不足、观点分歧、过期、部分成功保持区分，不放宽方向或证据校验，不把补数据等同买入信号。
- 改写前备份/tmp/litchi-analysis-failure-backup，原子写入。未改凭据、资金默认值、模型或数据源，未调用付费生成。

## 验证

- 后端TDD 8失败/2通过复现；修复后111项专项通过、修改模块pyright与ruff通过。
- 前端TDD复现错误分类；24项相关消费者/SSR组件测试通过（旧wrapped402、全失败、空、未知原因、部分成功、无自动调用、无原文泄露）。类型和eslint通过。
- CUA临时页已显示588110旧23:02失败记录及余额原因；22:32旧研究仍可选择。未点任何AI生成或更新按钮。
- 首轮全套在风控向后兼容测试阻塞：该测试只mock模型，遗漏DataCollector注入，进入真实行情采集。仅终止该pytest进程并补空采集桩；未中断应用服务或模型研究。前端既有ETF消费者fixture同步新增组件依赖及成功分析记录。
- 最终`python scripts/check.py --diff 4756ee4`六项闸门全绿（ruff、pyright src/backend、README同步、2793 passed / 7 skipped / 19 deselected、前端lint、类型）；`pnpm test`全部327通过。详细日志：/tmp/litchi-analysis-failure-gates-final.log与/tmp/litchi-analysis-failure-all-ui-final.log。
- 无活跃研究后优雅重启唯一后端PID54313→58867，前端PID75951原位热更新；/api/health与前端均200，OpenAPI可见两项新错误码。未POST研究接口，未执行真实模型调用。原新闻后台按原配置运行。
- 生产会话只读核验：deb_3b829df108cd payload SHA256仍为71d2afa4f78e4e46f2e6b590b4be7bb8c0d301d92bdeca491dc9d8ee538ff49e；最新两份研究时间与ID未变。
- 浏览器证据：/Users/lvsongyuan/.codex/visualizations/2026/10/22/01a16378-2360-7510-bdf8-a53ec339e688/etf-debate-balance-failure.jpg。
- 文档、引用清理、债务与学习卡78已同步；DEBATE-FAILURE-001与QA-RISK-ISOLATION-20261104当轮关闭，开放代码债务净增0。本地提交，不推送。

## 外部条件和后续

- 当前配置模型账户返回余额不足，代码修复不等于模型账户恢复；需要账户持有人处理后手动发起新的研究。没有自动充值、切换供应商或重跑。
- 本轮不实现全局账户熔断，不取消已在执行的其他分析；单次余额失败不做内部重试。历史原始状态保留供审计，显示侧纠正。
