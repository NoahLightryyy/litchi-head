# 37｜不可变 K 线证据：为什么“存过”不等于“可审计回放”

## 一句话

> 可审计回放必须同时锁住数据内容、来源诊断、采集时间和权威版本，并在任何一环
> 缺失或被改动时失败关闭。

---

## 为什么需要它？

### 问题场景

如果只把最终 K 线覆盖写进一张表，后来无法回答：当时两家来源各返回了什么、哪次
请求是否截断、使用了哪个交易日历和状态检查点。更危险的是，数据库索引时间若被
改早，未来采集的证据可能被历史 `as_of` 查询提前看见。

```text
只存最终结果
  → 丢失逐源 RAW 和失败诊断
  → 无法证明当时为什么放行或拒绝
  → 回测可能无意读取未来版本
```

### 它的解法

项目把一个逻辑快照拆成两层：SQLite 保存不可变清单和检索索引，Parquet 保存逐源
RAW 与规范结果。Parquet 文件名是内容 SHA-256；清单也有逻辑快照哈希。成员先耐久
发布，SQLite 清单最后事务提交，因此半写入不会成为可见快照。

回放不是只执行 `WHERE collected_at <= as_of`。读取后还会重新计算成员哈希、清单
哈希和逻辑快照 ID，并交叉核对数据库选择列、清单内请求和真实采集时间。

---

## 项目里的真实代码

打开 `src/data/kline_store.py`：

```python
snapshot = KlineEvidenceSnapshot.model_validate(
    snapshot.model_dump(mode="python", exclude={"snapshot_id"})
)

if _sha256(raw) != member.content_hash:
    raise KlineAuditStoreError("K-line audit member hash mismatch")

if not selector_matches or snapshot.collected_at > as_of_utc:
    raise KlineAuditStoreError(
        "K-line audit selector or as_of integrity mismatch"
    )
```

第一段在持久化边界重新验证输入，防止 Pydantic 对象构造后被修改而绕过校验。第二段
拒绝被替换的 Parquet。第三段防止只篡改 SQLite 索引时间造成未来证据穿越。

---

## 和普通缓存有什么不同？

| 对比 | 普通缓存 | 审计快照 |
|:-----|:---------|:---------|
| 写入语义 | 新值可覆盖旧值 | 追加不可变、重复写幂等 |
| 损坏处理 | 可回源或忽略 | 显式失败关闭 |
| 时间语义 | 取“最新” | 只取 `as_of` 当时已知版本 |
| 保存内容 | 常只存最终值 | RAW、诊断、版本引用、规范结果 |
| 用途 | 加速 | 复盘、回测、责任追踪 |

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_kline_audit_store.py -q`；
2. 找到“篡改 selector 暴露未来快照”的测试，观察它只改 SQLite 时间字段；
3. 找到成员篡改、缺失和锁定测试，确认都抛出 `KlineAuditStoreError`；
4. 思考：为什么最新快照损坏时不能静默回退旧快照？

---

**上一篇：[36｜K 线事实与复权](36-raw-adjusted-kline-evidence.md)**

**相关：[30｜可恢复 Session 信封](30-durable-session-envelope.md)**

**下一篇：[38｜K 线覆盖证明](38-kline-coverage-proof.md)**
