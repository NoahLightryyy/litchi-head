# 75｜提醒要代替用户做整理，不能代替行情做事实

一句话：把保存的研究翻译成用户能理解的提醒，同时保留它原来的时间和条件。

## 项目真实代码

`frontend/lib/watchlist-reminders.ts` 校验股票身份、报价与已有研究，只有GET读取，不暗中付费生成。
`frontend/components/stock/watch-reminders.tsx` 将waiting翻译成“买入条件还没凑齐”，但明确条件未实时重查。
行情变化是观察，历史计划是过去判断，两者不能合并成“现在可以买”。失败时保留已有内容和原时间。
`frontend/app/watchlist/page.tsx` 让用户只选股票；备注选填，旧v1记录照常读取，每页最多挂载10只的行情查询。
`backend/routers/stocks.py` 在目录失效时用已有公司资料核对完整代码；单股报价不能证明这是股票而非ETF。

## 自己试试（5分钟）

1. 运行前端watchlist-reminders测试，检查不同代码、基金类型和乱序历史被如何处理。
2. 打开自选页，搜索完整代码，直接加入，不填写任何研究问题。
3. 比较报价时间和已保存分析时间，展开具体条件，检查有没有把旧结论冒充实时信号。
4. 检查网络失败后页面是否保留已保存的备注和原有信息。

上一篇：[74 产业环节与企业身份](74-chain-company-identity.md)。

下一篇：[76 自动市场观察与榜单解读](76-observation-and-ranking-context.md)。
