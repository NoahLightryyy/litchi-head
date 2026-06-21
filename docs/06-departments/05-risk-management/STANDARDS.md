# 📐 风控管理部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的风控模块特定规范。

---

## 代码规范

### 风险评估接口

```python
# ✅ 正确：结构化风险评估
class RiskAssessment(BaseModel):
    overall_risk: str = Field(description="整体风险等级: low/moderate/high/critical")
    max_drawdown_risk: float = Field(ge=0, le=1, description="最大回撤风险评估 0-1")
    concentration_risk: float = Field(ge=0, le=1, description="集中度风险 0-1")
    volatility_risk: float = Field(ge=0, le=1, description="波动率风险 0-1")
    alerts: list[str] = Field(description="风险警告列表")
    passed: bool = Field(description="是否通过风控检查")
    
# ❌ 禁止：纯文本风险描述
return {"risk": "风险较高"}  # 无法量化、无法比较
```

### RiskProfile 配置化

```python
# ✅ 正确：风控阈值从 RiskProfile 读取
class RiskProfile(BaseModel):
    max_drawdown_pct: float = Field(default=20.0, ge=0, le=100)
    max_single_position_pct: float = Field(default=30.0, ge=0, le=100)
    min_confidence_threshold: float = Field(default=0.4, ge=0, le=1)
    
# ❌ 禁止：硬编码阈值
if drawdown > 20:  # 这个 20 是哪来的？
    return "高风险"
```

### 风控独立性

```python
# ✅ 正确：风控独立判断，不依赖辩论结果格式
def evaluate(self, state: DebateState) -> RiskAssessment:
    profile = state.risk_profile  # 从 state 读配置
    assessment = self._calc_risk(state.debate_output, profile)
    return assessment

# ❌ 禁止：风控修改辩论结果
def evaluate(self, state: DebateState) -> RiskAssessment:
    if self._is_high_risk(state):
        state.debate_output.decision = "观望"  # 禁止：修改辩论结果
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `orchestrator.py` | 488 | **600** | ✅ |
| `profiles.py` | 180 | **400** | ✅ |
| `models.py` | — | **400** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ 低风险决策通过风控
- ✅ 高风险决策被标记 **不通过**
- ✅ 边界值风控（回撤刚好 20.0%，置信度刚好 0.4）
- ✅ RiskProfile 不同配置的输出差异
- ✅ 风控不修改辩论结果（只读检查）
- ✅ 每种风险维度单独测试

### 覆盖率目标

- 风控编排器：≥85%
- 风险画像：≥90%
- 风险评估计算：≥90%

---

## 性能标准

| 指标 | 目标 |
|:-----|:----:|
| 单次风险评估 | ≤ 50ms |
| RiskProfile 加载 | ≤ 5ms |
| 多维度同时评估（5 因子） | ≤ 100ms |

---

## 部门间契约

### 输入契约（依赖辩论引擎部）

```python
# 风控需要的辩论输出字段
class RiskInput(BaseModel):
    decision: str                # 辩论决策
    confidence: float            # 置信度
    target_stock: str            # 目标股票
    suggested_position: float    # 建议仓位 %
```

### 输出契约（提供给辩论引擎部 + 交易执行部）

```python
class RiskAssessment(BaseModel):
    overall_risk: str            # low/moderate/high/critical
    passed: bool                 # 是否通过
    max_drawdown_risk: float     # 0-1
    concentration_risk: float    # 0-1
    volatility_risk: float       # 0-1
    alerts: list[str]            # 警告消息
    assessed_at: datetime        # 评估时间
```

---

## 审查清单

- [ ] 风险评估结构化（非纯文本）？
- [ ] 阈值从 RiskProfile 读取，非硬编码？
- [ ] 风控不修改辩论结果？
- [ ] LLM 调用经过 `llm.py`？
- [ ] 测试覆盖所有风险维度？
- [ ] 高风险有日志警告？
