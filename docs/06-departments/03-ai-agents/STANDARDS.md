# 📐 AI Agent 架构部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的 Agent 特定规范。

---

## 代码规范

### BaseAgent 设计

```python
# ✅ 正确：基类只定义骨架，业务层继承
class BaseAgent(ABC):
    """所有 Agent 的基类"""
    
    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult:
        """子类必须实现"""
        ...

# ❌ 禁止：基类塞业务逻辑
class BaseAgent(ABC):
    async def run(self, ctx):
        if "茅台" in ctx.query:  # 禁止：业务逻辑在基类
            return SpecialResult(...)
```

### AgentResult 泛型

```python
# ✅ 正确：泛型化输出
class AgentResult(BaseModel, Generic[T]):
    success: bool = True
    data: T | dict = Field(default_factory=dict)
    error: str | None = None

# ✅ 使用方式
class NewsOutput(BaseModel):
    summary: str
    sentiment: str

result = AgentResult[NewsOutput](data=NewsOutput(...))
result.data.summary  # Pyright 可校验

# ❌ 禁止：裸 dict
result = AgentResult(data={"summary": "..."})  # 无法类型校验
```

### 通信协议

```python
# ✅ 正确：走 MessageRouter
message = AgentMessage(
    sender="buffett",
    receiver="munger",
    content="关于茅台你怎么看？",
    message_type=MessageType.QUERY,
)
router.send(message)

# ❌ 禁止：Agent 之间直接调用
class BuffettAgent:
    async def ask_munger(self):
        munger = MungerAgent()  # 禁止：硬编码依赖
        return await munger.analyze("茅台")
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `base.py` | 140 | **500** | ✅ |
| `master_agent.py` | 232 | **500** | ✅ |
| `xiao_zhi.py` | — | **500** | ✅ |
| `protocol.py` | — | **500** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ Agent 正常执行返回结构化结果
- ✅ Agent 执行中 LLM 抛异常
- ✅ AgentResult 泛型类型校验（Pyright 通过）
- ✅ MessageRouter 消息投递
- ✅ MasterAgent Skill 插件盘加载/卸载
- ✅ 向后兼容：旧版 `AgentResult(data=dict)` 仍可用

### 覆盖率目标

- 基类：≥90%
- MasterAgent：≥85%
- 通信协议：≥90%

---

## 性能和兼容性标准

| 指标 | 目标 |
|:-----|:----:|
| Agent 实例化开销 | ≤ 10ms |
| MessageRouter 消息投递 | ≤ 1ms |
| AgentResult 序列化 | ≤ 5ms |
| 旧版 `AgentResult(dict)` 兼容 | ✅ 全测试通过 |

---

## 部门间契约

### 提供给辩论引擎部的接口

```python
# Agent 基类 — 辩论引擎部继承此定义大师 Agent
class MasterAgent(BaseAgent):
    """通用大师 Agent"""
    persona: str            # 人格定义（如：价值投资）
    skill_disk: SkillDisk   # 加载技能插件
    
    async def analyze(self, ctx: AgentContext) -> AgentResult:
        ...
```

### Agent 注册规范

```python
# 所有 Agent 必须在 AGENT_REGISTRY 注册
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "buffett": BuffettAgent,
    "munger": MungerAgent,
    "druckenmiller": DruckenmillerAgent,
    # ... 新增 Agent 必须加在这里
}
```

---

## 审查清单

- [ ] 新增 Agent 继承 BaseAgent？
- [ ] AgentResult 使用泛型而非裸 dict？
- [ ] 基类无业务逻辑？
- [ ] 通信不走 MessageRouter？
- [ ] 新 Agent 已在 AGENT_REGISTRY 注册？
- [ ] 向后兼容旧版 `AgentResult(data=dict)`？
