# 16 系统性代码按察 — Silent Failure 审计方法论

## 一句话

> 实盘系统最大的坑不是已知 bug，而是**你不知道自己漏了什么**。按察（代码审计）就是主动找出"没人发现但迟早出事"的静默异常。

---

## 为什么需要它？

### 问题场景

`except: pass` 这个词是实盘系统里最危险的三个字。

看这段代码：

```python
try:
    klines = collector.get_klines(code)
except Exception as e:
    logger.warning("K线数据获取失败: %s", e)
```

这段代码没写 `pass`，但它仍然存在隐患——`logger.warning` **不记录堆栈**。调试时你只知道"失败了"，但不知道在哪里、什么参数、哪个调用链。线上排查等于盲人摸象。

更糟的情况：

```python
try:
    risk_round = RiskRoundResult(**rr_raw)
except Exception:
    risk_round = RiskRoundResult()  # 异常完全吞掉
```

PM 做风控决策时，异常被静默吞掉，系统继续"正常"运行——但实际是基于一个空对象做交易决策。**你爸妈在亏钱，代码一句日志都没有。**

### 它的解法

**按察审计（Code Quality Sweep）**——三路并行探针，系统性扫描全代码库：

1. **结构探针** — 列出所有 try/except，检查每个 catch 块是否有日志
2. **错误模式探针** — 搜索静默吞异常、`get("key")` 无默认值、返回空值不记日志
3. **测试探针** — 检查测试覆盖了错误路径还是只有快乐路径

输出三份报告，合并后按严重程度排序，每一条 CRITICAL 必须修。

---

## 项目里的真实代码

打开 `src/debate/orchestrator.py` 行 622：

```python
except Exception:
    # 失败时返回默认值，不阻塞流程
    return RebuttalAnalysis(
        agent_name=f"master.{skill.skill_id}",
    )
```

**审计发现**：`_run_rebuttal` 是 LLM 调用，可能因为超时、API 错误、JSON 解析失败等多种原因出错。开发人员加了"不阻塞流程"的兜底，但**完全没记录异常**。线上 100 次失败也无人知道。

**修复后**：

```python
except Exception:
    logger.exception("RebuttalAnalysis 生成失败: agent=master.%s", skill.skill_id)
    # 失败时返回默认值，不阻塞流程
    return RebuttalAnalysis(
        agent_name=f"master.{skill.skill_id}",
    )
```

打开 `tests/test_data_models.py` 行 143：

```python
class TestEdgeCases:
    """边界条件测试 — 负值/零值/极值"""

    def test_stock_quote_negative_price(self):
        """负价格应被拒绝"""
        with pytest.raises(ValidationError):
            StockQuote(
                code="000001", name="测试", price=-1.0,
                change=0.0, change_pct=0.0, volume=1000,
            )
```

**审计前**：数据模型没有 `Field(ge=0.0)` 约束，负股价、负交易量可以通过验证。
**审计后**：`StockQuote.price` 加了 `Field(ge=0.0)`，KLine 加了 `model_validator` 验证 OHLC 合理性。

---

## 按察检查清单（每次审计必查）

| 类别 | 检查项 | 严重程度 |
|:-----|:-------|:--------:|
| 静默失败 | `except:` 块内有 `pass` 吗？ | 🔴 CRITICAL |
| 静默失败 | `except Exception:` 块内有 `logger.exception()` 吗？ | 🔴 CRITICAL |
| 静默失败 | `logger.warning("msg")` 缺 `str(e)` 吗？ | 🔴 CRITICAL |
| 静默失败 | 返回 `[]`/`None` 的路径记日志了吗？ | 🔴 CRITICAL |
| 类型安全 | 新增 `# type: ignore` 带错误代码了吗？ | 🟡 MAJOR |
| 类型安全 | 函数缺返回类型注解？ | 🟡 MAJOR |
| 边界条件 | Pydantic 字段有 `Field(ge=/le=)` 约束吗？ | 🟡 MAJOR |
| 边界条件 | 测试覆盖空输入/None/网络错误了吗？ | 🟡 MAJOR |
| 硬编码 | 价格/URL/路径可以从配置读取吗？ | 🟢 MINOR |
| 硬编码 | magic number 有注释解释吗？ | 🟢 MINOR |

### 严重程度定义

| 级别 | 含义 | 行动 |
|:----:|:-----|:----:|
| 🔴 CRITICAL | 出错了没人知道，用户可能在亏钱 | **立即修复** |
| 🟡 MAJOR | 不是立即危险，但积累导致可维护性崩溃 | **登记债务，安排修复** |
| 🟢 MINOR | 最佳实践不完美 | **登记债务，有时间修** |

---

## Audit 工作流

```
┌─ 1. 并行探针（3 路同时跑）────────────────┐
│  Agent A: 文件结构 + try/except 分布      │
│  Agent B: 静默失败模式 + 错误处理缺口       │
│  Agent C: 测试质量 + 边界条件覆盖           │
├─ 2. 综合报告 ───────────────────────────┤
│  按 severity 排序所有发现问题              │
│  标注每个问题的文件路径 + 行号             │
├─ 3. Phase 1: 修 CRITICAL ──────────────┤
│  必须：logger.exception() 补全            │
│  必须：except:pass 消除                  │
├─ 4. Phase 2: 登记债务 ────────────────┤
│  CRITICAL 已修复 → CLOSED.md            │
│  MAJOR/MINOR 未修 → 对应类型文件          │
├─ 5. Phase 3: 补测试 ──────────────────┤
│  边界条件测试（负值/空/None/网络错误）     │
│  LLM 错误路径测试                        │
├─ 6. Phase 4: 规则升级 ────────────────┤
│  Hookify 规则补漏（如有新发现的模式）      │
└─────────────────────────────────────────┘
```

---

## 面试会怎么问

> **Q: 你们怎么做线上问题的代码审计？**
>
> A: 我们是三路并行的自动化扫描。第一路看 try/except 分布，第二路搜静默失败模式，第三路看测试有没有覆盖错误路径。三份报告合并后按严重程度排优先级，CRITICAL 的必须修，MAJOR 的登记债务排期。

> **Q: logger.exception 和 logger.warning 有什么区别？**
>
> A: `logger.exception` 会自动在日志中附加当前异常的完整堆栈跟踪（traceback），让你知道从哪条调用链产生的错误。`logger.warning` 只记录你传的消息。在 `except` 块里应该永远用 `logger.exception`，除非你确定不需要 traceback。

---

## 自己试试（5 分钟）

1. 打开 `src/debate/orchestrator.py`，搜索 `except Exception`
2. 数一数现在多少个 `except` 块有 `logger.exception()`？多少个没有？
3. 打开 `src/data/models.py`，看看 `StockQuote` 和 `KLine` 的 `Field(ge=...)` 约束
4. 思考题：如果你加一个新数据源，应该检查哪三个地方确保它不会静默吞异常？

---

**上一篇：[Hookify 规则与 Claude Code Hooks](15-hookify-rules.md)** ← 持续质量保障的前置防线

**下一篇：**（等你写下一张卡片）
