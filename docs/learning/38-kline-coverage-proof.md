# 38｜K 线覆盖证明：返回了数据，不等于覆盖了请求

## 一句话

> 长窗完整性必须由每个独立来源分别证明；不能用两个来源各自的一半拼成“双源完整”。

---

## 为什么需要它？

新浪的免费日线端点可能忽略历史起止日期，只返回最近一段；腾讯则能接受日期窗口，
但长区间需要分段查询。如果只检查“返回行数大于零”，一个 2010～2026 的请求可能
只拿到最近几年，却被误送入 AI。

项目因此保存每次上游请求的范围、完成时间、准确响应字节数、SHA-256 和行数：

- 腾讯把长窗拆成不超过 1000 个自然日的连续分段，分段之间不能有缝；
- 新浪只有最早原始日期不晚于请求起点时才证明完整；
- 后续分段或行解析失败时，先前有效 RAW 仍作为诊断保存，但不能成为 canonical；
- 完整快照要求每个成功来源独立覆盖全部 canonical 日期、每个日期恰好一根，
  且同日价格、成交量和成交额通过统一精度规则对账。
- canonical 不能任选“容差内都算对”的候选；运行时和存储共同按成交量精度、
  是否有成交额、成交额精度和稳定来源 ID 选择同一根，保证相同 RAW 只有一个
  snapshot 结果。

```text
新浪：7/28 ────── 缺 7/29
腾讯：缺 7/28 ─── 7/29
并集：7/28 + 7/29

结论：仍然不完整；两个半段不能拼成双源证明。
```

---

## 项目里的真实代码

打开 `src/data/providers/kline.py`：

- `SinaRawDailyKlineSource.fetch_audited()` 判断响应是否覆盖请求起点；
- `TencentRawDailyKlineSource.fetch_audited()` 生成连续分段和准确响应证明。

打开 `src/data/kline_store.py`：

- `KlineEvidenceSnapshot.validate_snapshot()` 在持久化边界再次验证每个成功来源的
  日期集合、重复日期、同日冲突、日历权威和 canonical RAW 血缘。

打开 `src/data/kline.py`：

- `raw_daily_bar_conflict()` 是运行时和存储边界共用的价格/量额对账规则，避免
  两处规则慢慢漂移。
- `select_canonical_raw_daily_bar()` 是两处共用的确定性最佳精度选择规则。

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_kline_long_window.py -q`；
2. 找到新浪 recent-tail 与腾讯连续分段测试；
3. 运行 `python -m pytest tests/test_data/test_kline_audit_store.py -q`；
4. 找到 split-source、duplicate-date 和 source-conflict 三个测试；
5. 思考：为什么失败快照值得保存部分 RAW，却绝不能暴露 canonical？

---

**上一篇：[37｜不可变 K 线证据](37-immutable-kline-audit-replay.md)**

**相关：[36｜K 线事实与复权](36-raw-adjusted-kline-evidence.md)**
