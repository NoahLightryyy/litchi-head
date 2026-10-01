# 59 本机记录：校验、持久化与恢复

## 一句话

浏览器存储是可能损坏或写失败的外部输入；恢复备份前先验证全部内容，失败时保留原记录。

## 为什么需要它

自选与持仓承载用户自己填写的数据。JSON能解析不等于代码、金额、日期有效；把损坏记录当空数组再保存会丢失数据。两个存储键也不具备数据库事务能力。

## 项目里的真实代码

- `frontend/lib/portfolio.ts`的parseHoldings校验类型、非负有限金额、真实日历日期和唯一ID，未知成本保留null。
- `frontend/lib/hooks/use-holdings.ts`使用useSyncExternalStore订阅跨页面/标签变化。读错阻止覆盖，写错显示原因且允许重试。
- `frontend/lib/personal-backup.ts`在任何写入前验证两份记录，第二次写失败则回滚先前值；回滚失败明确报告，不能称为完全原子事务。
- `frontend/app/portfolio/page.tsx`提交日期使用FormData读取原生日期控件，避免显示值与React事件状态不同步。
- tsconfig的allowImportingTsExtensions配合noEmit，使备份纯函数既可被Next打包，也能由Node直接执行TypeScript测试。

## 自己试试（3—5分钟）

1. 在独立预览录入一条标明测试的持仓，成本留空，确认没有虚构收益。
2. 刷新页面，再编辑成本，检查差额；移除并撤销后清理测试记录。
3. 运行`npm test`，观察模拟第二个键写失败后两份原记录均恢复的测试。

上一篇：[58 并发截止](58-bounded-sync-upstream-concurrency.md)。后续卡片见[索引](README.md)。

## 补充：接口边界也要做真实消费者验收

`frontend/lib/intraday-contract.ts`会拒绝缺字段，不能把HTTP200等同于可展示。`backend/routers/evidence.py`区分usable（可展示原始单源点）和complete（满足双源策略）。`src/data/collector.py`不缓存空K线，让重试真正触达数据源。真实浏览器验收发现旧信封时，应对齐后端模型并提交契约，不能删掉前端校验。

2026-09-20：frontend/lib/debate-error.ts按服务端错误码区分证据门禁、限流和断线，未知错误不输出原始上游内容；个股页面各模块独立失败，不让报价失败吞掉已有分时证据。

备用数据也要验证语义：frontend/lib/raw-daily.ts同时核对代码、raw口径、1d周期、严格日期顺序及OHLC。backend/kline_display.py通过独立信封保留来源和日期，不把备用RAW塞入既有前复权接口。图表只接收真实OHLC与成交量，不将未知成交额补零。

图表也有默认视窗状态：candlestick-chart.tsx在setData之后调用timeScale().fitContent()，否则64根默认宽度的K线会集中在右侧。成交量独立比例尺隐藏最后值/价格线，避免体量标签与价格轴混读。数据语义标签留在图旁，长限制移到details。
# 下一篇

[60｜时间范围缩放](60-semantic-price-zoom.md)
