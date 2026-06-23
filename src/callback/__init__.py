"""结果参数回调引擎

该引擎提供一个中心化的回调事件分发系统，当辩论结果、用户操作、
回测结果等事件发生时，自动触发参数调整回调。

用法:
    from src.callback import CallbackEventType

    engine = ResultCallbackEngine(memory_store=store)
    await engine.dispatch(CallbackEventType.DEBATE_COMPLETED, ...)

RC-001 实现时会解除注释并创建 engine.py、callbacks/ 目录。
"""

# RC-001 待实现: from src.callback.engine import ResultCallbackEngine
from src.callback.models import (
    CallbackConfig,
    CallbackEvent,
    CallbackEventType,
    CallbackRecord,
)
from src.callback.registry import CallbackRegistry
from src.callback.storage import CallbackStorage

__all__ = [
    # "ResultCallbackEngine",  # RC-001 实现时解封
    "CallbackRegistry",
    "CallbackStorage",
    "CallbackConfig",
    "CallbackEvent",
    "CallbackEventType",
    "CallbackRecord",
]
