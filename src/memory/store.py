"""命名空间记忆存储系统（MemoryStore 接口 + JsonFileStore 实现）"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    """存储层返回的记忆条目

    通过 namespace 区分记忆类型和所属 Agent/用户。
    score 字段为 search() 结果的相关性评分（JSON 存储默认为 0.0，向量存储返回相似度）。
    """

    key: str
    value: Any
    namespace: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    score: float = 0.0
