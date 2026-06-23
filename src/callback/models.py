"""结果参数回调引擎的数据契约

定义事件类型、事件负载、回调配置和执行记录模型。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field


class CallbackEventType(str, Enum):
    """回调事件类型

    每个枚举成员代表一个可触发回调的系统事件。
    事件分类：
      - MARKET_*: 市场结果相关（辩论结果、回测结果）
      - USER_*: 用户操作相关
      - SYSTEM_*: 系统事件（启动、关闭）
    """

    # -- 市场结果 --
    DEBATE_COMPLETED = "debate_completed"
    ACTUAL_OUTCOME_RECEIVED = "actual_outcome_received"
    BACKTEST_COMPLETED = "backtest_completed"
    TRADE_SETTLED = "trade_settled"

    # -- 用户操作 --
    USER_ACTION_RECORDED = "user_action_recorded"
    USER_PREFERENCE_CHANGED = "user_preference_changed"

    # -- 系统 --
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


class CallbackEvent(BaseModel):
    """回调事件

    当系统事件发生时由调度点创建，包含触发回调所需的所有上下文数据。
    数据以通用 dict 格式携带，每个回调实现提取其所需的部分。
    """

    event_type: CallbackEventType
    source: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    context: dict[str, Any] = Field(default_factory=dict)


class CallbackPriority(int, Enum):
    """回调执行优先级

    优先级仅排序执行顺序，不阻断（所有回调均独立执行）。
    """

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class CallbackConfig(BaseModel):
    """每个回调的运行时配置

    持久化在 ("callback", "config") 命名空间下，key 为回调名称。
    支持在不修改代码的情况下启用/禁用/调整单个回调。
    """

    callback_name: str
    enabled: bool = True
    event_types: list[CallbackEventType] = Field(default_factory=list)
    cooldown_seconds: int = 0
    priority: CallbackPriority = CallbackPriority.NORMAL
    params: dict[str, Any] = Field(default_factory=dict)
    last_fired_at: datetime | None = None
    error_count: int = 0
    max_errors_before_disable: int = 5


class CallbackRecord(BaseModel):
    """单次回调执行记录

    存储每个回调执行的输入/输出/状态，用于审计、调试和去重。
    """

    callback_name: str = ""
    event_type: CallbackEventType = CallbackEventType.SYSTEM_STARTUP
    event_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_ms: float = 0.0
    success: bool = True
    summary: str = ""
    mutations: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


# -- 回调签名类型 --
CallbackFn = Callable[
    [CallbackEvent],
    Coroutine[Any, Any, CallbackRecord],
]

__all__ = [
    "CallbackEventType",
    "CallbackEvent",
    "CallbackPriority",
    "CallbackConfig",
    "CallbackRecord",
    "CallbackFn",
]
