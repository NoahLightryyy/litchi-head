"""预置结果回调注册入口"""

from __future__ import annotations

from src.callback.callbacks.m3_ext import create_m3_ext_callback, register_m3_ext_callback

__all__ = [
    "create_m3_ext_callback",
    "register_m3_ext_callback",
]
