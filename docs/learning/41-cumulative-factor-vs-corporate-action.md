# 41 累计复权因子：为什么一串 QFQ 数字还不是公司行动

## 一句话

> 新浪累计前复权除数能证明供应商如何缩放历史价格，但只有与独立官方公司行动公告匹配后，才能成为可进入点时复权的事件因子。

---

## 为什么需要它？

新浪 `qfq.js` 返回的是按日期变化的累计除数。它适合证明某个响应版本下，供应商
把 RAW 历史价除以多少；但它没有可靠地给出“这是现金分红还是送股”、精确股本
比例和公告修订时间。

若直接把累计值当作 `CorporateActionFactor.price_factor`，会同时犯两个错误：

```text
累计除数：older = 1.0329067641682, newer = 1

错误：把 1.0329 直接乘到历史价格
正确候选事件乘数：newer / older ≈ 0.9681
最终可用：还必须匹配同一除权日的 CNINFO/交易所正式条款
```

因此项目把两个阶段隔离：

1. `QfqFactorSnapshot` 保存新浪原始响应和累计除数证据；
2. 未来 KR-2B-2 用独立官方公告确认事件，再生成 `CorporateActionFactor`。

代码层也使用两个不同能力名：新浪快照只声明 `CUMULATIVE_QFQ_FACTOR`，可被
KR-2B-2 标准证据链消费；只有未来完成官方事件核验的组合源才能声明
`CORPORATE_ACTION_FACTOR`。

北交所即使新浪端点有数据，只要官方事件核验链未完成，也在网络请求前返回
`official_verification_unavailable`。

---

## 项目里的真实代码

打开 `src/data/providers/sina_adjustment.py`：

```python
if market_code_for(request.stock_code) is MarketCode.BSE:
    return SourceResult(
        status=SourceStatus.UNSUPPORTED,
        error_code="official_verification_unavailable",
        ...
    )
```

适配器还保存 `response_hash`、`response_bytes`、`adapter_version`、原始 Decimal
精度和 `1900-01-01` 基准哨兵。`src/data/kline_adjustment.py` 的模型再检查：

```python
if self.factor_version != f"sha256:{self.response_hash}":
    raise ValueError("factor_version must identify the response hash")
```

这使“供应商当时返回了什么”和“官方事件是否足以生成复权因子”成为两条可分别
审计的证据链。

---

## 和公司行动因子有什么不同？

| 对比 | 累计 QFQ 快照 | `CorporateActionFactor` |
|:-----|:--------------|:------------------------|
| 含义 | 供应商累计价格除数 | 单次已核验公司行动的价量乘数 |
| 来源 | 新浪直连 | 新浪相邻累计值 + 独立官方事件 |
| 事件类型/股本比例 | 不可信或没有 | 必须来自 CNINFO/交易所条款 |
| 能否直接进入 AI/回测 | 不能 | 通过完整性门禁后才可以 |

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_sina_adjustment_provider.py -q`；
2. 把合法样本的最新累计值从 `1` 改成 `1.1`，确认锚点校验失败；
3. 用测试中的北交所代码确认 fetcher 没有被调用；
4. 计算 `1 / 1.0329067641682`，思考为什么事件类型和量因子仍不能从这个比值推断。

---

## 前后链接

- 上一张：[40｜点时复权](40-point-in-time-adjustment.md)
- 下一张：待新增
