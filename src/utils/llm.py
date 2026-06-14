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

    # 自定义 LLM 参数（TD-012）
    config = LLMConfig(temperature=0.7, max_tokens=4096)
    reply = await llm_service.ainvoke("分析", llm_config=config)

    # 自动复杂度路由（TD-014）
    reply = await llm_service.ainvoke_auto("分析市场情绪", agent_name="analyst")

    # 强制使用推理模式（复杂任务）
    config = LLMConfig(model="deepseek-reasoner", reasoning_effort="medium")
    reply = await llm_service.ainvoke("深度分析", llm_config=config)
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
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


# ── LLMConfig ──────────────────────────────────────────────


@dataclass(frozen=True)
class LLMConfig:
    """LLM 调用配置 —— 定义一次调用的模型参数

    默认值与当前硬编码值（temperature=0.3, max_tokens=8192）一致，
    不传或传 None 时行为完全不变（向后兼容）。
    """

    temperature: float = 0.3
    max_tokens: int = 8192
    model: str | None = None          # None = 用 provider 默认模型
    stream: bool = False
    reasoning_effort: str | None = None  # DeepSeek 推理强度标识

    @property
    def is_default(self) -> bool:
        """是否与当前硬编码默认值一致

        用于缓存策略判断：默认配置按 provider 缓存，
        非默认配置每次都新建实例。
        """
        return (
            self.model is None          # 显式指定 model → 非默认
            and self.temperature == 0.3
            and self.max_tokens == 8192
            and self.stream is False
            and self.reasoning_effort is None
        )


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


def _build_llm(
    provider: str | None = None,
    config: LLMConfig | None = None,
) -> BaseChatModel:
    """根据 provider + 配置创建 LLM 实例

    Args:
        provider: "deepseek" | "openai"，默认使用 settings.llm_provider
        config: LLM 调用配置，None 或默认值 = 当前硬编码行为

    Returns:
        BaseChatModel 实例

    Raises:
        ValueError: provider 不受支持
        RuntimeError: 缺少对应 API Key
    """
    provider = provider or settings.llm_provider
    cfg = config or LLMConfig()

    match provider:
        case "deepseek":
            if not settings.deepseek_api_key:
                raise RuntimeError(
                    "DEEPSEEK_API_KEY 未设置，请在 .env 中配置"
                )
            model = cfg.model or "deepseek-chat"
            kwargs: dict[str, Any] = {
                "model": model,
                "model_kwargs": {"max_tokens": cfg.max_tokens},
            }
            # deepseek-reasoner 不支持 temperature 参数
            if "reasoner" not in model:
                kwargs["temperature"] = cfg.temperature
            # reasoning_effort 仅对 reasoner 模型生效
            if cfg.reasoning_effort and "reasoner" in model:
                kwargs["model_kwargs"]["reasoning_effort"] = cfg.reasoning_effort
            return ChatDeepSeek(**kwargs)
        case "openai":
            if not settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY 未设置，请在 .env 中配置"
                )
            return ChatOpenAI(
                model=cfg.model or "gpt-4o-mini",
                temperature=cfg.temperature,
                model_kwargs={"max_tokens": cfg.max_tokens},
            )
        case "anthropic":
            api_key = settings.anthropic_api_key or settings.anthropic_auth_token
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN 未设置，请在 .env 中配置"
                )
            # 惰性导入：langchain_anthropic 仅在使用时加载（TD-012）
            try:
                from langchain_anthropic import ChatAnthropic  # type: ignore  # noqa: I001
            except ImportError:
                raise RuntimeError(
                    "使用 Anthropic provider 需要安装 langchain-anthropic："
                    "pip install langchain-anthropic"
                )
            kwargs: dict[str, Any] = {
                "model": cfg.model or "claude-sonnet-4-20250514",
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "api_key": api_key,
            }
            if settings.anthropic_base_url:
                kwargs["base_url"] = settings.anthropic_base_url
            return ChatAnthropic(**kwargs)
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
    1. 管理 LLM 实例（按 provider 创建/缓存，config 感知）
    2. 提供文本调用和结构化输出两种接口
    3. 自动记录 token 用量和费用
    4. 网络错误时自动重试（指数退避）
    """

    def __init__(self) -> None:
        self._instances: dict[str, BaseChatModel] = {}

    # ── 实例管理 ──────────────────────────────────────────

    def get_llm(
        self,
        provider: str | None = None,
        config: LLMConfig | None = None,
    ) -> BaseChatModel:
        """获取 LLM 实例（配置感知的缓存策略）

        缓存策略：
        - config=None 或 config.is_default → 按 provider 缓存（与当前行为一致）
        - config 非默认值 → 每次都新建（不同 Agent 不同 temperature 不冲突）
        """
        provider = provider or settings.llm_provider

        # 非默认配置 → 不缓存，每次新建
        if config is not None and not config.is_default:
            return _build_llm(provider, config)

        # 默认配置/无配置 → 按 provider 缓存
        if provider not in self._instances:
            self._instances[provider] = _build_llm(provider, config)
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
        llm_config: LLMConfig | None = None,
    ) -> str:
        """纯文本调用（无结构化输出）

        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词
            provider: 模型提供商，默认使用 settings.llm_provider
            agent_name: Agent 名称（用于费用记录）
            session_id: 会话 ID（用于费用记录）
            llm_config: LLM 调用配置，None 或默认值 = 当前行为

        Returns:
            模型返回的文本内容
        """
        llm = self.get_llm(provider, llm_config)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        response = await self._call_with_retry(llm, messages)
        _record_usage(llm, response, agent_name, session_id)
        return response.content

    # ── 流式调用 ─────────────────────────────────────────

    async def astream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
        llm_config: LLMConfig | None = None,
    ) -> AsyncIterator[str]:
        """流式文本调用，逐 token 返回内容

        使用 LLM 的 astream 方法逐 token 实时输出。
        流结束后记录 token 用量（当前使用 fallback 值）。

        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词
            provider: 模型提供商，默认使用 settings.llm_provider
            agent_name: Agent 名称（用于费用记录）
            session_id: 会话 ID（用于费用记录）
            llm_config: LLM 调用配置

        Yields:
            模型返回的文本片段

        Examples:
            async for chunk in llm_service.astream("你好"):
                print(chunk, end="")
        """
        llm = self.get_llm(provider, llm_config)
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        async for chunk in llm.astream(messages):
            content = chunk.content if isinstance(chunk.content, str) else ""
            if content:
                yield content

        # 流结束后记录费用（当前使用 fallback，无法获取准确 token 用量）
        if agent_name != "unknown":
            _record_usage(
                llm,
                _FALLBACK_RESPONSE,
                agent_name,
                session_id,
            )

    # ── 自动复杂度路由 ─────────────────────────────────────

    async def ainvoke_auto(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
        base_config: LLMConfig | None = None,
    ) -> str:
        """自动检测复杂度 + 路由到最优模型（TD-014）

        简单问题 → deepseek-chat（快速，无推理开销）
        复杂问题 → deepseek-reasoner（深度推理模式）

        仅对 DeepSeek provider 生效；其他 provider 直接透传。

        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词
            provider: 模型提供商，默认使用 settings.llm_provider
            agent_name: Agent 名称（用于费用记录）
            session_id: 会话 ID（用于费用记录）
            base_config: 基础 LLM 配置（temperature 等），路由会在此基础上调整

        Returns:
            模型返回的文本内容

        Examples:
            # 自动路由（推荐）
            reply = await llm_service.ainvoke_auto("分析市场情绪")

            # 需要强制推理模式时，显式传入 LLMConfig
            config = LLMConfig(model="deepseek-reasoner", reasoning_effort="high")
            reply = await llm_service.ainvoke("复杂分析", llm_config=config)
        """
        provider = provider or settings.llm_provider

        # 非 DeepSeek provider → 直接透传，不做复杂度路由
        if provider != "deepseek":
            return await self.ainvoke(
                prompt=prompt,
                system_prompt=system_prompt,
                provider=provider,
                agent_name=agent_name,
                session_id=session_id,
                llm_config=base_config,
            )

        # DeepSeek provider → 复杂度检测 + 路由
        from src.utils.complexity_router import complexity_router

        llm_config, result = complexity_router.route(
            prompt=prompt,
            system_prompt=system_prompt,
            base_config=base_config,
        )

        model_label = "reasoner" if "reasoner" in (llm_config.model or "") else "chat"
        logger.info(
            f"[auto-route] complexity={result.complexity.value} "
            f"score={result.score:.2f} model={model_label} "
            f"reasons={result.reasons}"
        )

        return await self.ainvoke(
            prompt=prompt,
            system_prompt=system_prompt,
            provider=provider,
            agent_name=agent_name,
            session_id=session_id,
            llm_config=llm_config,
        )

    # ── 结构化输出 ────────────────────────────────────────

    async def invoke_structured(
        self,
        prompt: str,
        output_model: type[BaseModel],
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
        llm_config: LLMConfig | None = None,
    ) -> BaseModel:
        """带结构化输出的 LLM 调用

        Args:
            prompt: 用户提示词
            output_model: Pydantic 模型类，定义输出结构
            system_prompt: 可选的系统提示词
            provider: 模型提供商，默认使用 settings.llm_provider
            agent_name: Agent 名称（用于费用记录）
            session_id: 会话 ID（用于费用记录）
            llm_config: LLM 调用配置，None 或默认值 = 当前行为

        Returns:
            output_model 的实例（已验证）

        Raises:
            ValueError: LLM 返回内容无法解析为 output_model
        """
        llm = self.get_llm(provider, llm_config)
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
