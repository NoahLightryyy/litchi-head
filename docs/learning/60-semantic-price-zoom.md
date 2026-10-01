# 60｜时间范围缩放：换视图不等于造数据

一句话：缩放到当前数据边界后切换真实数据集，让当日分时、五日分时和日 K 承载不同时间尺度。

## 项目真实代码

- `frontend/lib/chart-zoom.ts`：范围限制、最新窗口右端锚定、250ms 手势间隔；一次连续滚动最多切一级。历史窗口放大不会自动跳到最近五日。
- `frontend/components/stock/intraday-battlefield-panel.tsx`：统一窗口状态和按钮；当日数据失败不阻止其他窗口独立请求。
- `backend/intraday_display.py`：从已有腾讯历史分钟接口读取最多五个交易日。核验代码、日历、价格与时间，缺失点不补造。展示契约不改变 SHADOW 证据门禁。
- `frontend/lib/five-day-display.ts`：再次校验响应身份、排序、日期范围、数值与单源属性。

连续画线只连接真实端点。休市时间压缩不代表夜间成交，五日分时不能由五个日收盘价插值出来，也不能称为五日均线。单源可展示不等于多源已核验。

图表的 `fitContent` 解决初始范围；滚轮边界控制解决后续越缩越空。仅测试状态函数不够，还需要浏览器滚轮验收，确认图表库的半根柱宽和边界舍入不会让窗口逐渐偏离最新日。

API 参考：[ITimeScaleApi](https://tradingview.github.io/lightweight-charts/docs/4.2/api/interfaces/ITimeScaleApi)、[TimeScaleOptions](https://tradingview.github.io/lightweight-charts/docs/4.2/api/interfaces/TimeScaleOptions)。

## 自己试试（5 分钟）

1. 在 frontend 运行 `node --experimental-strip-types --test tests/chart-zoom.test.mts`。
2. 打开个股页，在当日分时内向下滚动，观察五日分时日期和实际点数。
3. 停下滚轮后再次缩小，观察同一区域切为日 K；放大最近日期验证返回。
4. 比较 `days` 与 `incomplete_days`：来源缺分钟时，为什么不能补成完整的 242 点？

上一篇：[59｜本机记录](59-local-record-validation.md)
