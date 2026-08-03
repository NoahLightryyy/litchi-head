# 44｜影子回填：有历史数据，不等于能直接生成实盘信号

## 一句话

> 单源历史先保存、后验证；只有满足正式证据契约的数据才能进入 Relative Volume。

---

## 为什么需要它？

腾讯能返回最近五日分钟曲线，但新浪的分钟分组与它不同，实测累计量偏差最高约
1.26%。给两者随意设置百分比容差，会把“口径不同”伪装成“核验通过”。成熟方案
通常选定一个规范行情口径，并把交易时段、停牌、无成交分钟和修订规则固定下来。

项目因此把数据分成两层：

- `single_source_shadow`：允许回填和回放，但不影响真金白银相关信号；
- `dual_source_verified`：东方财富与腾讯实时逐分钟门禁通过的完整交易日。

## 项目里的真实代码

打开 `src/data/intraday_history.py`：

```python
selected = list(unique.values())[:20]
values = [same_minute.cumulative_volume for session in selected]
baseline = TimeOfDayVolumeBaseline(
    as_of_minute=clock.strftime("%H:%M"),
    sample_days=len(values),
    expected_cumulative_volume=float(median(values)),
)
```

正式层只读取最近20个可信完整日。每个会话必须覆盖242个常规分钟、累计值单调且
最终成交量为正；Parquet 成员或 SQLite 清单哈希不一致时直接失败。

`src/data/providers/intraday_history.py` 会过滤15:00后的上游扩展行，将“手”乘100
归一化为“股”，但仍把腾讯历史标记为影子数据。API 通过
`relative_volume_backfill_shadow_only` 告诉用户：历史已保存，但尚未获准用于信号。

## 和“两个来源取平均”有什么不同？

| 做法 | 风险 | 本项目处理 |
|:-----|:-----|:-----------|
| 两源直接取平均 | 混合不同分钟定义 | 禁止 |
| 放宽到经验百分比容差 | 容易把系统偏差当噪声 | 禁止 |
| 单源直接出信号 | 用户看不见证据降级 | 只进影子层 |
| 正式层 + 影子验证 | 上线慢一些，但边界可审计 | 采用 |

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_intraday_history.py -q`；
2. 把测试中的一个常规分钟删掉，观察会话校验失败；
3. 把影子会话改成 `VERIFIED` 但只保留一个来源，观察模型拒绝；
4. 思考：若停牌日被填成242根零成交 bar，中位数会怎样误导 Relative Volume？

---

**上一篇：[43｜公告正文解析](43-corporate-action-document-parsing.md)**
