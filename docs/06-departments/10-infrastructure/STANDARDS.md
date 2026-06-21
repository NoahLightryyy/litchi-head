# 📐 基础设施部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的基础设施特定规范。

---

## 代码规范

### LLM 服务封装

```python
# ✅ 正确：统一调用入口
from src.utils.llm import LLMService, LLMConfig

service = LLMService()
config = LLMConfig(
    model="deepseek-chat",
    temperature=0.7,
    max_tokens=4096,
)
result = await service.agenerate(prompt, config=config)

# ❌ 禁止：其他模块直接实例化 LLM 客户端
from langchain_deepseek import ChatDeepSeek  # 禁止！
llm = ChatDeepSeek(model="deepseek-chat")    # 禁止！
result = llm.invoke(prompt)                  # 禁止！
```

### 配置管理

```python
# ✅ 正确：Pydantic Settings 统一管理
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    log_level: str = Field(default="INFO")
    
    @model_validator(mode="after")
    def validate_keys(self):
        if not any([self.deepseek_api_key, self.openai_api_key, self.anthropic_api_key]):
            logger.warning("未配置任何 LLM API Key")
        return self

# ❌ 禁止：硬编码配置
api_key = "sk-xxx"  # 禁止！
```

### LLMConfig 参数化

```python
# ✅ 正确：调用方传入参数
config = LLMConfig(
    model="deepseek-chat",
    temperature=0.3,       # 分析类任务用低温度
    max_tokens=4096,
)

# 或使用默认值（简单查询）
config = LLMConfig()  # 使用当前最优默认值

# ❌ 禁止：在 llm.py 中硬编码业务默认值
class LLMService:
    async def agenerate(self, prompt, temperature=0.7):  # 禁止：给什么默认值由调用方决定
        ...
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `llm.py` | 513 | **600** | ✅ |
| `complexity_router.py` | 303 | **400** | ✅ |
| `config.py` | — | **300** | ✅ |
| `cost_tracker.py` | — | **300** | ✅ |
| `logger.py` | — | **200** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ LLMService 正常生成回复
- ✅ LLMService 网络超时/异常降级
- ✅ LLMConfig 不同参数生效
- ✅ 多 Provider 切换（DeepSeek ↔ OpenAI）
- ✅ CostTracker token 计数准确
- ✅ CostTracker 费用计算准确
- ✅ Settings 环境变量加载优先级
- ✅ Settings 缺失 Key 时的行为
- ✅ ComplexityRouter 简单/复杂路由判断

### Mock 策略

```python
# LLM 调用使用 mocker.patch，不要实际调 API
def test_llm_timeout(mocker):
    mock_invoke = mocker.patch(
        "langchain_deepseek.ChatDeepSeek.invoke",
        side_effect=TimeoutError("API timeout"),
    )
    service = LLMService()
    with pytest.raises(LLMError):
        await service.agenerate("test", LLMConfig())
```

### 覆盖率目标

- LLMService：≥90%
- CostTracker：≥90%
- Settings/Config：≥90%
- ComplexityRouter：≥85%

---

## 性能标准

| 指标 | 目标 |
|:-----|:----:|
| LLMService 封装开销（不含模型推理）| ≤ 10ms |
| CostTracker 记录一笔 | ≤ 1ms |
| Settings 加载 | ≤ 100ms（首次）|
| ComplexityRouter 判断 | ≤ 5ms |

---

## 变更通知协议

基础设施部是最底层依赖。变更影响面最大，必须通知全部门。

### 变更等级

| 等级 | 示例 | 通知范围 |
|:-----|:-----|:---------|
| 🔴 **BREAKING** | LLMService 公开 API 签名变更 | **通知所有部门** + 全量回归测试 |
| 🟡 **非兼容** | 新增 Provider 支持、CostTracker 增加字段 | 通知辩论引擎部 + 后端 API 部 |
| 🟢 **内部** | logger 格式调整、内部工具函数 | 无需通知 |

### 🔴 BREAKING 变更流程

```
1. 在当前分支改 llm.py
2. 运行全量测试 → 看哪里崩了
3. 逐个修复调用方（临时，保证可运行）
4. 通知所有部门负责人："LLMService.agenerate 签名变了"
5. 提 PR → 审 → 合
6. 各部门回归验证
```

---

## 多 Provider 支持

```python
# ✅ 正确：当前支持的 Provider
SUPPORTED_PROVIDERS = {
    "deepseek": {"env_key": "DEEPSEEK_API_KEY", "model": "deepseek-chat"},
    "openai": {"env_key": "OPENAI_API_KEY", "model": "gpt-4o"},
    "anthropic": {"env_key": "ANTHROPIC_API_KEY", "model": "claude-sonnet-4-6"},
}

# 加载优先级：deepseek → openai → anthropic
# 按配置顺序尝试，第一个有 API Key 的作为默认
```

---

## 审查清单

- [ ] 无硬编码 API Key？
- [ ] LLMService 封装不夹杂业务逻辑？
- [ ] 所有异常向上抛出（不吞）？
- [ ] CostTracker 记录每笔调用？
- [ ] 多 Provider 至少一个可工作？
- [ ] 性能兜底（封装开销 ≤ 10ms）？
- [ ] 🔴 等级变更通知了所有部门？
- [ ] 向后兼容（非必要不做 breaking change）？
