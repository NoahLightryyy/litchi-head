"""LLM 调用封装层 —— 所有 Agent 的 LLM 调用必经此层

用法:
    from src.utils.llm import llm_service

    # 简单文本调用
    reply = await llm_service.ainvoke("你好")

    # 结构化输出
    class Analysis(BaseModel):
        sentiment: str
        score: float
    result = await llm_service.invoke_structured(
        prompt="分析市场情绪",
        output_model=Analysis,
        agent_name="news_agent",
    )
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.config import settings
from src.utils.cost_tracker import cost_tracker
from src.utils.logger import AgentLogger

logger = AgentLogger("llm_service")

# 结构化输出调用无法获取 BaseMessage，用于占位费用记录
_FALLBACK_RESPONSE = HumanMessage(content="")

# ── 异常重试配置 ─────────────────────────────────────────────

_RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    ValueError,
)


def _build_retry_decorator() -> Any:
    """构建带指数退避的重试装饰器"""
    return retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
        before=before_log(logger.logger, logger.logger.level),
        after=after_log(logger.logger, logger.logger.level),
    )


# ── LLM 实例工厂 ─────────────────────────────────────────────


def _build_llm(provider: str | None = None) -> BaseChatModel:
    """根据 provider 创建 LLM 实例

    Args:
        provider: "deepseek" | "openai"，默认使用 settings.llm_provider

    Returns:
        BaseChatModel 实例

    Raises:
        ValueError: provider 不受支持
        RuntimeError: 缺少对应 API Key
    """
    provider = provider or settings.llm_provider

    match provider:
        case "deepseek":
            if not settings.deepseek_api_key:
                raise RuntimeError(
                    "DEEPSEEK_API_KEY 未设置，请在 .env 中配置"
                )
            return ChatDeepSeek(
                model="deepseek-chat",
                temperature=0.3,
                model_kwargs={"max_tokens": 8192},
            )
        case "openai":
            if not settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY 未设置，请在 .env 中配置"
                )
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                model_kwargs={"max_tokens": 8192},
            )
        case _:
            raise ValueError(f"不支持的 LLM provider: {provider}")


# ── Token 用量记录 ────────────────────────────────────────────


def _record_usage(
    llm: BaseChatModel,
    response: BaseMessage,
    agent_name: str,
    session_id: str,
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    """记录 LLM 调用费用

    优先从 response.response_metadata 读取 token 用量，
    未提供时使用 fallback 值。
    """
    model_name = getattr(llm, "model", "unknown")
    meta = getattr(response, "response_metadata", {}) or {}
    token_usage = meta.get("token_usage", meta.get("usage", {}) or {})

    pt = prompt_tokens or token_usage.get("prompt_tokens", 0) or 0
    ct = completion_tokens or token_usage.get("completion_tokens", 0) or 0

    cost_tracker.record(
        model=model_name,
        prompt_tokens=pt,
        completion_tokens=ct,
        agent=agent_name,
        session_id=session_id,
    )


# ── LLMService ────────────────────────────────────────────────


class LLMService:
    """统一的 LLM 调用入口

    职责：
    1. 管理 LLM 实例（按 provider 创建/缓存）
    2. 提供文本调用和结构化输出两种接口
    3. 自动记录 token 用量和费用
    4. 网络错误时自动重试（指数退避）
    """

    def __init__(self) -> None:
        self._instances: dict[str, BaseChatModel] = {}

    # ── 实例管理 ──────────────────────────────────────────

    def get_llm(self, provider: str | None = None) -> BaseChatModel:
        """获取 LLM 实例（带缓存）

        相同 provider 复用同一实例（减少重复初始化开销）。
        """
        provider = provider or settings.llm_provider
        if provider not in self._instances:
            self._instances[provider] = _build_llm(provider)
        return self._instances[provider]

    def clear_cache(self) -> None:
        """清空 LLM 实例缓存（provider 切换或配置更新时调用）"""
        self._instances.clear()
        logger.info("LLM 实例缓存已清空")

    # ── 基础调用 ──────────────────────────────────────────

    async def ainvoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
    ) -> str:
        """纯文本调用（无结构化输出）

        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词
            provider: 模型提供商，默认使用 settings.llm_provider
            agent_name: Agent 名称（用于费用记录）
            session_id: 会话 ID（用于费用记录）

        Returns:
            模型返回的文本内容
        """
        llm = self.get_llm(provider)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        response = await self._call_with_retry(llm, messages)
        _record_usage(llm, response, agent_name, session_id)
        return response.content

    # ── 结构化输出 ────────────────────────────────────────

    async def invoke_structured(
        self,
        prompt: str,
        output_model: type[BaseModel],
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
    ) -> BaseModel:
        """带结构化输出的 LLM 调用

        Args:
            prompt: 用户提示词
            output_model: Pydantic 模型类，定义输出结构
            system_prompt: 可选的系统提示词
            provider: 模型提供商，默认使用 settings.llm_provider
            agent_name: Agent 名称（用于费用记录）
            session_id: 会话 ID（用于费用记录）

        Returns:
            output_model 的实例（已验证）

        Raises:
            ValueError: LLM 返回内容无法解析为 output_model
        """
        llm = self.get_llm(provider)
        structured_llm = llm.with_structured_output(output_model, include_raw=False)

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        try:
            result = await self._call_with_retry(structured_llm, messages)
        except Exception as e:
            raise ValueError(
                f"LLM 结构化输出解析失败 for {output_model.__name__}: {e}"
            ) from e

        if not isinstance(result, output_model):
            raise ValueError(
                f"LLM 返回类型不匹配：期望 {output_model.__name__}，"
                f"实际 {type(result).__name__}"
            )

        # 结构化调用不返回 BaseMessage，无法获取 token 用量
        if agent_name != "unknown":
            _record_usage(
                llm,
                _FALLBACK_RESPONSE,
                agent_name,
                session_id,
            )

        return result

    # ── 内部重试逻辑 ──────────────────────────────────────

    @staticmethod
    async def _call_with_retry(
        runnable: Any,
        messages: list,
    ) -> Any:
        """带 retry 的异步调用

        tenacity 装饰器处理可重试异常，
        不可重试的异常（如 KeyError）直接透传。
        """
        retry_decorator = _build_retry_decorator()

        @retry_decorator
        async def _do_call() -> Any:
            return await runnable.ainvoke(messages)

        return await _do_call()


# ── 全局单例 ────────────────────────────────────────────────

llm_service = LLMService()
