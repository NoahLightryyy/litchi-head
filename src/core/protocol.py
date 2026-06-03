"""Agent 间通信协议 —— 结构化消息格式"""

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """证据链中的一条引用"""
    source: str
    source_message_id: str
    summary: str


MessageType = Literal["proposal", "challenge", "response", "vote", "command", "report"]


class AgentMessage(BaseModel):
    """Agent 间通信的标准消息格式"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    receiver: str
    message_type: MessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str
    payload: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_chain: list[EvidenceItem] = Field(default_factory=list)

    def to_json_schema(self) -> dict:
        """导出 JSON Schema"""
        return self.model_json_schema()


class MessageRouter:
    """消息路由器 —— 管理消息的收发和追踪"""

    def __init__(self):
        self._messages: dict[str, AgentMessage] = {}

    def send(self, message: AgentMessage) -> str:
        """发送消息，返回 message_id"""
        self._messages[message.message_id] = message
        return message.message_id

    def get(self, message_id: str) -> AgentMessage | None:
        return self._messages.get(message_id)

    def get_by_session(self, session_id: str) -> list[AgentMessage]:
        return [m for m in self._messages.values() if m.session_id == session_id]

    def get_by_sender(self, agent_name: str) -> list[AgentMessage]:
        return [m for m in self._messages.values() if m.sender == agent_name]

    def clear_session(self, session_id: str):
        self._messages = {
            k: v for k, v in self._messages.items()
            if v.session_id != session_id
        }


message_router = MessageRouter()
