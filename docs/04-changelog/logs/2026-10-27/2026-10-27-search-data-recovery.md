# 2026-10-27 股票目录、名称搜索与混合诊断恢复

## 恢复与范围

本聊天 `codex/market-availability`，起点8167ad1；session_state inspect为MATCH，核对Git、HANDOVER、WORKLIST与service-recovery日志后执行用户新提出的首页/京泉华搜索缺陷。初始工作区仅既有frontend/node_modules链接，未启动重复模型/测试/服务。本轮不新增数据源、不使用LLM、不改资金风险参数、不推送。

## 根因：网络与代码分别说明

1. 新浪行情出现DNS解析失败；东方财富报价HTTP502，腾讯指数接口此前成功、后续又出现HTTP501。它们是真实外部请求失败，未证明是供应商本身或本机代理中的哪一层产生，不隐瞒、不以改文案声称网络恢复。
2. 旧AKShare聚合目录按沪市→深市→科创板→北交所串行获取；首请求失败就退出。单独探测既有深市接口返回2906条，其中京泉华002885；同轮聚合接口连接被重置。
3. Provider把异常吞为[]，Collector按成功key缓存一小时。网络恢复后还会读旧空目录。
4. 搜索表单提交只写历史，同词按钮不refetch。混合故障中，两个可替代指数源失败与一个目录问题被计成3项异常。

## 实现

- 新增内部StockCatalogSnapshot与分市场有界加载：每市场最多一个在途任务，成功各缓存1小时，失败15秒退避，等待8秒先返回可用部分；晚到结果在下次请求收取。
- Collector成功缓存与部分/失败退避分离，废弃旧空成功缓存，记录完整性和诊断code；兼容列表入口保留。
- 两个搜索API继续既有HTTP结构，返回可信部分身份而不冒充完整目录。目录不完整且股票搜索没有匹配仍503；discovery的failed_sources保留对应来源。
- 前端同词搜索/重新搜索真正请求，防抖切词不请求旧词，在途不重复；不完整目录无匹配不宣称股票不存在。
- 诊断按业务问题/备用失败分组；保留真正价格冲突。后端连通但数据受限与连接失败分开显示。

## 验收

- TDD：旧collector/provider冷却恢复测试先失败；原组件同词提交refetch为0；原混合异常显示3而非1。修复后通过。
- 最终 `python scripts/check.py` **6/6通过**：Ruff、Pyright零错误、README同步、backend/data模块测试、前端lint与TypeScript。
- Python **1426 passed / 4 skipped**；前端 `npm test` **283 passed**。包含慢市场限时返回/并发不重复、恢复/缓存、空及坏代码、部分目录匹配、旧空缓存、前端同词请求与诊断分组。跳过项不计成功。
- 首次check启动因PATH缺ruff退出；修正为原venv与既有Node路径后最终全通过，没有安装依赖。此前一次check在格式修复前Ruff失败，修好后最终复验通过。
- 真实HTTP：`/api/discovery/search?q=京泉华`200，8.38秒，京泉华002885，failed_sources含股票目录/ETF目录；此时仅北交所未完成，其余5224身份已可用。`/api/stocks/search`同词200，market=sz。
- 浏览器同词“重新搜索”后四市场目录完成：data仍匹配002885，failed_sources仅ETF目录；all_stocks current_status=healthy，历史failures=1保留，不再有股票目录警告。
- 真实浏览器能点击搜索结果跳转 `/stock/002885`。该详情报价仍受外部接口故障影响，未声称行情已恢复，未点击任何AI生成。最后返回搜索结果页。
- 截图 `/tmp/litchi-search-recovered.png`；测试日志 `/tmp/litchi-search-data-recovery-check.log`、`/tmp/litchi-data-recovery-frontend-tests.log`。

## 部署与剩余边界

替换前再次核对辩论13 completed / 2 failed、政策1 failed，无活跃研究，日志无新模型调用。仅重启本聊天8000后端：旧PID75949→80357，独立后台会话，继续读取原项目data/.env与工作树代码；3000前端75950/75951未重启、HMR更新。没有改系统DNS/代理或电源配置。

SDK底层不可强杀的请求仍可能永久占用其单槽位，非当前adata/FallbackSource配置仍需部分结果适配；已登记DATA-CATALOG-TRANSPORT-001，不扩大本次改动。数据目录恢复债务DATA-CATALOG-RECOVERY-001、前端FW-SEARCH-RECOVERY-001已关闭；ENV-DNS-20261027与既有服务生命周期债务仍开放。

已同步HANDOVER/WORKLIST/README、后端交接契约、学习卡56、债务索引。全项目搜索旧stock_info_a_code_name引用：生产入口与集成探测已更新；原历史工作日志和新适配器说明保留作为追溯。代码更改前备份在 `/var/folders/hh/fjhkskjj6rb077gbnh5t1f9h0000gn/T/litchi-data-recovery-backup-moo4k0tw`，不覆盖既有用户改动。

本地提交后保存会话快照；没有新功能方向时仅轻量状态确认，不重复付费生成、不重复启动服务。回滚使用本提交的git revert并在无活跃分析时重载后端，历史研究数据不在改动范围。
