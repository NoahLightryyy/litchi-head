"""Agent 基类 —— 所有 Agent 的统一接口"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.protocol import AgentMessage
from src.utils.config import settings
from src.utils.logger import AgentLogger


@dataclass
class AgentContext:
    """Agent 运行的上下文"""
    session_id: str
    input_data: dict
    memory: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent 的标准输出格式"""
    agent_name: str = ""
    session_id: str = ""
    success: bool = True
    data: dict = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    error: Optional[str] = None
    latency_ms: float = 0.0

    def to_message(self) -> AgentMessage:
        return AgentMessage(
            sender=self.agent_name,
            receiver="orchestrator",
            message_type="report",
            session_id=self.session_id,
            payload={
                "success": self.success,
                "data": self.data,
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
