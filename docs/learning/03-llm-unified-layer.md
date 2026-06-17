# 03 LLM 统一封装层

## 一句话

> `src/utils/llm.py` 是整个项目**所有 AI 调用的唯一出入口**。任何代码想调用 ChatGPT / DeepSeek，必须经过这个文件。这是项目的**交通管制**。

---

## 为什么要有统一层？

### 坏的做法（没有统一层）

```python
# 文件 A
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4", temperature=0.7)
result = llm.invoke("分析茅台")

# 文件 B  
from langchain_deepseek import ChatDeepSeek
llm2 = ChatDeepSeek(model="deepseek-chat", temperature=0.3)
result2 = llm2.invoke("分析五粮液")

# 文件 C
from openai import OpenAI
client = OpenAI()
result3 = client.chat.completions.create(...)
```

问题：
1. **模型切换**：想从 DeepSeek 换成 GPT，要改 10 个文件
2. **配置散落**：每个文件自己设 temperature，不一致
3. **费用不可追踪**：没人知道总共花了多少钱
4. **错误处理重复**：每个文件自己写 retry，或干脆不写

### 好的做法（统一层）

```python
# 所有文件都这样调
from src.utils.llm import llm_service

result = await llm_service.infer(
    system_prompt="你是资深分析师",
    user_prompt="分析茅台",
    response_model=AnalysisResult  # 结构化输出！
)
```

想换模型？改 `src/utils/llm.py` 一个文件就行。

---

## 项目里的真实设计

打开 `src/utils/llm.py`，核心结构：

```python
class LLMService:
    def __init__(self):
        # 根据配置选择模型
        self._model = self._select_model()

    def _select_model(self):
        if config.llm.provider == "deepseek":
            return ChatDeepSeek(model="deepseek-chat")
        elif config.llm.provider == "openai":
            return ChatOpenAI(model="gpt-4o")
        # fallback 链：一个失败自动换下一个

    async def infer(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel] = None,
    ) -> BaseModel | str:
        """所有 LLM 调用的统一入口"""
        # 1. 绑定 prompt
        # 2. 调用 LLM（自动重试 3 次）
        # 3. 解析结构化输出（如果有 response_model）
        # 4. 记录费用
        # 5. 返回结果
```

### 关键特性

**1. 结构化输出**
```python
class AnalysisResult(BaseModel):
    rating: str          # 买入/持有/卖出
    confidence: float    # 置信度
    reasoning: str       # 理由

result = await llm_service.infer(
    "分析这只股票",
    "茅台基本面...",
    response_model=AnalysisResult  # ← LLM 直接输出结构化数据
)
# result 直接是 AnalysisResult 实例
# result.rating, result.confidence, result.reasoning 直接用
```

**2. 自动重试**
网络波动时 LLM 调用会失败。统一层帮你自动重试 3 次，你不必在每个调用处写 try/except。

**3. 费用追踪**
每次调用自动记录花费，最后可以生成报表——"这周 AI 帮我分析了 500 次，花了 0.5 美元"。

---

## 统一层的五个好处

| 好处 | 没有统一层 | 有统一层 |
|:-----|:-----------|:---------|
| 换模型 | 改所有文件 | 改一个文件 |
| 重试 | 每个调用自己写 | 统一配，全项目生效 |
| 费用记录 | 没人知道花了多少钱 | 自动记，随时查 |
| 结构化输出 | 自己解析 JSON | 传入 model 自动搞定 |
| 错误处理 | for 循环里裸调用 | 统一 timeout + retry |

---

## 项目红线

> **CLAUDE.md 明确写死了："
> 所有 LLM 调用必经 `src/utils/llm.py`，不得直接实例化 ChatDeepSeek/ChatOpenAI
> "**

如果你在代码里看到：
```python
from langchain_deepseek import ChatDeepSeek  # ❌ 违规！
```

这就是违反红线。

---

## 自己试试（5 分钟）

1. 打开 `src/utils/llm.py`
2. 找到 `infer` 方法，辨认出：
   - [ ] 参数有哪些
   - [ ] 哪里做的 retry
   - [ ] 哪里记录的费用
3. 在全项目里搜索 `ChatDeepSeek` 或 `ChatOpenAI`：
   ```bash
   grep -r "ChatDeepSeek" src/ --include="*.py"
   ```
   应该**只有 `src/utils/llm.py` 出现**。如果其他地方也出现了，那就是违规。

---

**上一篇：[LangGraph StateGraph 编排](02-langgraph-stategraph.md)**

**下一篇：[FastAPI 桥接层架构](04-fastapi-bridge.md)** — Python 后端怎么和前端通信
