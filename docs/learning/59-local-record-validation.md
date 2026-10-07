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

复盘接入边界：`frontend/app/portfolio/page.tsx` 保存金额快照，不能据此重建成交数量、买入价或费用。`frontend/components/retro/retro-board.tsx` 的历史研究结果保留原始值，但接口没有样本有效性证明时不能把默认0的均值当校准质量。新事实账本应从明确的用户操作记录开始；失败和无记录必须分开，否则用户可能重复录入。

[60｜时间范围缩放](60-semantic-price-zoom.md)

### 搜索历史：只记明确操作

`frontend/lib/search-history.ts`限定20条、80字符、去空值和大小写去重；重复项移到
最前。搜索组件只在提交、点击历史或打开结果时保存，避免输入片段污染历史。
useSyncExternalStore通过稳定JSON快照连接浏览器存储，服务端使用空数组快照避免
水合不一致；同页自定义事件和跨标签storage事件同步。禁用写入时降为当前页面内存。
自己试试：搜索“半导体”后刷新，再点历史记录；删除单项，另一个同源标签也应同步。

### 排行榜需要先固定样本与周期

当前gainers取新浪单日涨幅前20候选，再读其报价。不能用这20只的历史收益代表
全市场三日排名：那会漏掉今天不在前20、但三日累计涨幅更大的股票。资金净额与
总流入也是不同指标；没有流出值时无法从净额反推总流入。UI必须说明实际周期。

### 周期榜单缓存必须包含指标和周期

`backend/discovery_rankings.py`内存缓存按(metric,period)，历史SQLite再加截止交易日。
上一交易日只读对应日期的单日收盘存档；不会拿当前榜重排序。前端解析器同时校验
metric/period/unit/end_date，防止快速切换后把3日人民币净额当成5日百分比。
自己试试：从最新切换近3日，再切总流入，确认旧榜消失，区间及缺口随选择改变。
资金净流入允许负数和真零；来源缺值用不可用状态，不能强制填0来凑排行榜。

### 提交检查中的跨时区测试

`tests/test_backend/test_kline_display.py` 用固定UTC时刻分别覆盖北京时间跨日前后，
比较带时区的截止时刻与“当前时刻减一天”。不要把北京时间的`.date()`与UTC的
`.date()`直接比较：同一瞬间可能分属不同日期，测试会随执行时间偶发失败。
自己试试：分别用UTC 03:00和19:00运行该测试，检查两次都严格保留一天的请求边界。
