# 61 不可变用户操作账本：点击一次，事实只能追加一次

## 一句话

> 用户操作是审计事实：用幂等键追加，不覆盖；未知价格和数量保留为 `null`，绝不补零。

---

## 为什么需要它？

旧复盘接口把 `user_action` 直接覆盖在一条可变记录上。重复点击、重试或后续修改会让
系统无法证明用户当时做了什么，也会把“辩论价到现价”的市场涨跌误解成账户盈亏。

解法是把每次操作保存为独立事件。`client_action_id` 在同一用户内唯一：同样事实重试
返回原事件，不同事实复用标识则冲突。价格缺失就是缺失，不参与收益计算。

---

## 项目里的真实代码

打开 `src/retro/user_action_ledger.py`：

```python
connection.execute("BEGIN IMMEDIATE")
existing = connection.execute(
    "SELECT request_fingerprint, payload_json FROM user_action_events "
    "WHERE user_id = ? AND client_action_id = ?",
    (user_id, action.client_action_id),
).fetchone()
```

事务把“检查再写入”变成一个不可分割步骤，因此五次并发重试也只产生一个事件。

---

## 和旧 RetroRecord 有什么不同？

| 对比 | 旧复盘字段 | 新事件账本 |
|:-----|:-----------|:-----------|
| 写入 | 覆盖同一记录 | 只追加 |
| 重试 | 可能重复或覆盖 | 幂等回放 |
| 未知金额 | 容易被默认值污染 | `null`，且零值被拒绝 |
| 收益语义 | 市场观察涨跌 | 本批不计算账户盈亏 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_retro/test_user_action_ledger.py -q`。
2. 找到并发重试测试，把并发数从 5 改成 20。
3. 思考题：为什么真实账户收益必须等待成交、费用和滑点协议，而不能用现价代替？

---

**上一篇：[时间范围缩放](60-semantic-price-zoom.md)**

**下一篇：待补充**
