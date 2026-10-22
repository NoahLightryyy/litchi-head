# 2026-10-18 政策栏目、本金对照与API小样本

## 授权与交付

用户要求将央视政策解读和不同本金策略对照做进前端，并先跑一轮小样本。已交付侧栏 `/policy`、`/capital`，无新增后端契约，无账户读取或交易。政策为2025年来源历史样例，未冒充实时新闻；本金比例、费率、最低订单均显式假设。

## 文件

新增 frontend/app/policy/page.tsx、frontend/app/capital/page.tsx、frontend/lib/capital-scenarios.ts、frontend/tests/capital-scenarios.test.mts；更新app-shell侧栏与README。新增 scripts/evaluate_research_smoke.py、tests/test_scripts/test_research_smoke.py，更新differentiation三份文档并保存实测报告、manifest/全部输出/summary。学习卡67、债务EVAL-ANSWER-001及路由同步。

## 实测

请求deepseek-v4-pro，经统一LLM服务，非思考模式、temperature0、max_tokens384；18次逻辑调用。A直接4/6，R独立回答后复核6/6，失败调用0。两次A为answer与reason矛盾，R修正。预留费用上界3.771117元，不是实际支出；实际账单未取得。非盲测、非保留集、非等预算、无投资收益标签，不构成正式排名。未修改交易默认值。

## 验证

项目 python scripts/check.py 全部通过5/5；前端Node测试139/139；新增评分pytest 1/1；Ruff与git diff --check通过。初测发现佣金浮点尾差299.99999999999994，改按分舍入后精确为300。

浏览器验证侧栏入口、政策展开假设/证据/反证；本金研究费120→30时月成本220/220/420→130/130/330，空输入隐藏表格并报错，恢复120。截图 `/private/tmp/litchi-policy-ready.png` 与 `/private/tmp/litchi-capital-ready.png`。

## 边界与后续

实时新闻抓取、自动观察、个性化账户策略未实现；正式评测需独立保留集、等预算、模型返回修订与实际用量审计。保留既有脏工作树，未提交或推送，未重启后端。旧文档“未执行付费评测”已改为完整协议未执行并链接本次缩小范围实测，旧日志按历史保留。
