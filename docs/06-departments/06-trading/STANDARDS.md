# 📐 交易执行部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的交易模块特定规范。

---

## 代码规范

### 交易模型

```python
# ✅ 正确：结构化交易模型
class TradePlan(BaseModel):
    action: str = Field(pattern="^(buy|sell|hold|wait)$", description="交易动作")
    stock_code: str = Field(min_length=6, max_length=6, description="股票代码")
    price: float = Field(ge=0, description="预期交易价格")
    quantity: int = Field(ge=0, description="交易数量")
    confidence: float = Field(ge=0, le=1, description="决策置信度")
    debate_id: str = Field(description="关联的辩论 ID，可追溯")
    
class TradeRecord(BaseModel):
    plan: TradePlan
    executed_price: float = Field(ge=0)
    executed_at: datetime
    status: str = Field(pattern="^(pending|executed|failed|cancelled)$")
    error: str | None = None

# ❌ 禁止：无校验的裸 dict
{"action": "buy", "stock": "000001"}  # 无法校验有效性
```

### 执行前的安全门禁

```python
# ✅ 正确：执行前检查
async def execute(self, plan: TradePlan, risk: RiskAssessment) -> TradeRecord:
    if not risk.passed:
        logger.warning("[Trader] 风控未通过，拒绝执行: %s", plan.stock_code)
        return TradeRecord(plan=plan, status="cancelled", ...)
    if plan.confidence < CONFIDENCE_THRESHOLD:
        logger.warning("[Trader] 置信度过低，拒绝执行: %f", plan.confidence)
        return TradeRecord(plan=plan, status="cancelled", ...)
    # 安全通过 → 执行
    ...

# ❌ 禁止：不检查直接执行
async def execute(self, plan):
    return await self._place_order(plan)  # 不检查风控、置信度
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `orchestrator.py` | 427 | **600** | ✅ |
| `bridge.py` | 260 | **400** | ✅ |
| `profiles.py` | — | **400** | ✅ |
| `models.py` | — | **400** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ TradePlan → TradeRecord 转换不丢字段
- ✅ 风控不通过时拒绝执行
- ✅ 置信度低于阈值时拒绝执行
- ✅ 执行失败回滚状态
- ✅ 交易记录可追溯到辩论 ID
- ✅ 数据一致性（Plan 和 Record 字段对齐）

### 覆盖率目标

- 执行编排：≥85%
- 桥接适配器：≥90%
- 交易模型：100%（模型字段验证）

---

## 性能标准

| 指标 | 目标 |
|:-----|:----:|
| TradePlan → TradeRecord 转换 | ≤ 5ms |
| 风控检查 + 执行 | ≤ 100ms |
| 交易记录序列化 | ≤ 5ms |

---

## 部门间契约

### 输入契约（依赖辩论引擎部 + 风控管理部）

```python
# 交易执行部需要以下两个输入才能执行
# 1. 辩论引擎部的 TradePlan
# 2. 风控管理部的 RiskAssessment
# 
# 两者缺一不可
```

### 输出契约（提供给回测研究部）

```python
# TradeRecord 是回测的输入数据
# 字段变更必须通知回测研究部
```

---

## 审查清单

- [ ] 执行前检查风控通过？
- [ ] 执行前检查置信度阈值？
- [ ] TradeRecord 不丢 TradePlan 字段？
- [ ] TradeRecord 有 debate_id 可追溯？
- [ ] 执行失败有状态回滚？
- [ ] 交易记录持久化？
- [ ] 风控不通过有日志？
