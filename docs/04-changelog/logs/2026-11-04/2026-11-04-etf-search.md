# 2026-11-04 ETF名称组合搜索修复

## 恢复与复现

- `codex/market-availability`，起点a942d41；session_state inspect为MATCH，核对实际Git、HANDOVER和上轮日志。原有frontend/node_modules软链接不暂存。
- 用户搜“半导体广发基金的ETF”找不到；实页“半导体广发”返回空。
- 原API按560780可查到“半导体设备ETF广发”，按半导体返回18条且包含560780：本次目录正常，根因为`query in name`只认连续顺序。

## 实现与边界

- 新增backend/discovery_matching.py，NFKC归一、ETF类别/助词清理、同候选主题/管理人组合匹配。
- 中文片段至少两字，动态规划覆盖整个查询，字符不能重复透支；数字/英文词精确命中。
- 搜索排序依次精确代码/名称、原包含匹配、ETF组合匹配。原响应schema、类型/代码去重、100条截断、total、失败目录提示不变。
- 不从搜索词猜身份、不新增来源/别名库、不调用模型。前端无需修改契约。
- 文件改写前备份于 `/tmp/litchi-etf-search-backup`，原子替换。清理发现契约与前端API文档漏列ETF的旧说明。

## 验收

- TDD先复现17失败/6通过；实现后专项与原搜索/ETF回归40通过。
- 全量ruff通过；初次pyright使用错误Python环境导致依赖缺失，显式指定原项目venv后src及修改模块零错误；后续完整闸门另记。
- 编码期间用户自己的deb_cd42e2dcd073研究仍在运行，因此没有直接重启后端，也没有新建服务或触发AI验收。
- 完整`python scripts/check.py --diff a942d41`通过6/6：全量ruff、src/backend pyright、README同步、590项后端测试、前端lint/type-check；8项前端搜索/历史/ETF消费者测试通过。新测试补充类型注解后专项23项再通过，格式修正后全量ruff通过。
- 原研究退出running后再次只读确认无running/queued任务，后端49041优雅退出，复用原配置/DB启动53149，无重复监听；前端75950/75951不重启。没有为本次搜索调用模型。
- 实网API三种词均HTTP200返回唯一560780“半导体设备ETF广发”。冷启动股票目录部分不可用仍保留failed_sources，但ETF结果正常，不将其混作ETF目录故障。
- 浏览器输入用户原话“半导体广发基金的ETF”，显示1项；点击进入/etf/560780并核对详情标题。保存截图etf-keyword-search.png于本聊天visualizations目录；临时验收页已关闭，用户原页未动。
- SEARCH-ETF-KEYWORDS-001关闭，外部股票目录覆盖问题保留既有诊断；未扩大到目录修复、主题别名推断或基金投资建议。

## 同步

契约、前端API说明、README、HANDOVER、债务SEARCH-ETF-KEYWORDS-001、学习卡77与索引已同步。无新增资金或风险默认值、系统设置修改、推送或真实交易。
