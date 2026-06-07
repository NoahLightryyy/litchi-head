"""Agent 基类 —— 所有 Agent 的统一接口"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel, Field

from src.utils.config import settings
from src.utils.logger import AgentLogger

if TYPE_CHECKING:
    from src.core.protocol import AgentMessage

# ──────────────────────────────────────────────
# 泛型类型变量
# ──────────────────────────────────────────────

T = TypeVar("T")


@dataclass
class AgentContext:
    """Agent 运行的上下文

    TD-014 新增辩论槽位：
    - peer_outputs: 辩论时接收其他 Agent 的输出
    - current_round: 当前辩论轮次
    - target_audience: 输出目标（"user" / "debate_group" / "master_vote"）

    向后兼容：三个字段均有默认值，现有代码不传则行为不变。
    """
    session_id: str
    input_data: dict
    peer_outputs: list["AgentResult"] = field(default_factory=list)
    current_round: int = 0
    target_audience: str = "user"
    memory: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


class AgentResult(BaseModel, Generic[T]):
    """Agent 的标准输出格式（Pydantic + 泛型）

    用法：
        AgentResult()                     → data: dict（向后兼容）
        AgentResult[NewsOutput](...)      → data: NewsOutput | dict

    泛型化后 Pyright 可静态校验：
        result.data.summary      ✅（Typed）
        result.data.non_existent ❌（编译报错）
    """
    agent_name: str = ""
    session_id: str = ""
    success: bool = True
    data: dict | T = Field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    error: str | None = None
    latency_ms: float = 0.0

    def to_message(self) -> "AgentMessage":
        # 延迟导入避免循环依赖
        from src.core.protocol import AgentMessage

        return AgentMessage(
            sender=self.agent_name,
            receiver="orchestrator",
            message_type="report",
            session_id=self.session_id,
            payload={
                "success": self.success,
                "data": self.data.model_dump() if isinstance(self.data, BaseModel) else self.data,
                "confidence": self.confidence,
                "reasoning": self.reasoning,
                "error": self.error,
            },
            confidence=self.confidence,
        )


class BaseAgent(ABC):
    """所有 Agent 的抽象基类"""

    def __init__(self, name: str, config: dict | None = None):
        self.name = name
        self.config = config or {}
        self.logger = AgentLogger(f"agent.{name}")

    def get_tools(self) -> list[Any]:
        """返回 Agent 可用的工具列表

        Phase 0 返回空列表，Phase 1 接入 LangChain Tool 时确定具体类型。
        ADR-009 约定：LangChain 0.3+ 的 Tool 类型跨版本有变化，
        因此返回 list[Any] 而非具体类型，避免后续升级困难。
        """
        return []

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult:
        """Agent 核心逻辑 —— 子类必须实现"""
        raise NotImplementedError

    async def run_safe(self, ctx: AgentContext) -> AgentResult:
        """带完整错误处理和超时控制的运行入口"""
        start = datetime.now()

        try:
            result = await asyncio.wait_for(
                self.run(ctx),
                timeout=settings.debate_timeout_seconds,
            )
            result.agent_name = self.name
            result.session_id = ctx.session_id
            result.success = True
        except asyncio.TimeoutError:
            self.logger.warning(f"超时 (>{settings.debate_timeout_seconds}s)")
            result = AgentResult(
                agent_name=self.name,
                session_id=ctx.session_id,
                success=False,
                error=f"执行超时 ({settings.debate_timeout_seconds}s)",
            )
        except Exception as e:
            self.logger.error(f"运行失败: {e}")
            result = AgentResult(
                agent_name=self.name,
                session_id=ctx.session_id,
                success=False,
                error=str(e),
            )

        elapsed = (datetime.now() - start).total_seconds() * 1000
        result.latency_ms = elapsed
        self.logger.info(f"完成 | 成功={result.success} | 耗时={elapsed:.0f}ms")
        return result
