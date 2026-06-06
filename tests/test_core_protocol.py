"""通信协议业务测试（TD-004 追认）"""

import pytest

from src.core.protocol import AgentMessage, EvidenceItem, MessageRouter

# ═══════════════════════════════════════════════════════════════════
# EvidenceItem
# ═══════════════════════════════════════════════════════════════════


class TestEvidenceItem:
    def test_has_required_fields(self):
        e = EvidenceItem(
            source="news_api",
            source_message_id="msg-001",
            summary="A股今日上涨",
        )
        assert e.source == "news_api"
        assert e.source_message_id == "msg-001"
        assert e.summary == "A股今日上涨"


# ═══════════════════════════════════════════════════════════════════
# AgentMessage
# ═══════════════════════════════════════════════════════════════════


class TestAgentMessage:
    def test_create_with_required_fields(self):
        msg = AgentMessage(
            sender="agent_a",
            receiver="agent_b",
            message_type="proposal",
            session_id="s1",
        )
        assert msg.sender == "agent_a"
        assert msg.receiver == "agent_b"
        assert msg.message_type == "proposal"
        assert msg.session_id == "s1"
        assert msg.confidence == 0.5
        assert msg.payload == {}
        assert msg.evidence_chain == []
        assert msg.message_id is not None
        assert len(msg.message_id) > 0

    def test_confidence_bounds(self):
        AgentMessage(
            sender="a", receiver="b", message_type="vote",
            session_id="s1", confidence=1.0,
        )
        AgentMessage(
            sender="a", receiver="b", message_type="vote",
            session_id="s1", confidence=0.0,
        )

    def test_confidence_out_of_bounds(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            AgentMessage(
                sender="a", receiver="b", message_type="vote",
                session_id="s1", confidence=1.5,
            )
        with pytest.raises(pydantic.ValidationError):
            AgentMessage(
                sender="a", receiver="b", message_type="vote",
                session_id="s1", confidence=-0.1,
            )

    def test_message_type_literal(self):
        for mt in ["proposal", "challenge", "response", "vote", "command", "report"]:
            msg = AgentMessage(
                sender="a", receiver="b", message_type=mt,  # type: ignore
                session_id="s1",
            )
            assert msg.message_type == mt

    def test_to_json_schema(self):
        msg = AgentMessage(
            sender="a", receiver="b", message_type="report",
            session_id="s1",
        )
        schema = msg.to_json_schema()
        assert schema["title"] == "AgentMessage"
        assert "properties" in schema
        assert "sender" in schema["properties"]

    def test_evidence_chain(self):
        ev = EvidenceItem(source="src", source_message_id="mid", summary="s")
        msg = AgentMessage(
            sender="a", receiver="b", message_type="proposal",
            session_id="s1", evidence_chain=[ev],
        )
        assert len(msg.evidence_chain) == 1
        assert msg.evidence_chain[0].source == "src"

    def test_message_id_unique(self):
        m1 = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        m2 = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        assert m1.message_id != m2.message_id

    def test_message_id_consistent(self):
        msg = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        mid = msg.message_id
        assert msg.message_id == mid  # 同一实例不变化


# ═══════════════════════════════════════════════════════════════════
# MessageRouter
# ═══════════════════════════════════════════════════════════════════


class TestMessageRouter:
    def test_send_returns_message_id(self):
        router = MessageRouter()
        msg = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        mid = router.send(msg)
        assert mid == msg.message_id

    def test_get_by_id(self):
        router = MessageRouter()
        msg = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        mid = router.send(msg)
        assert router.get(mid) is msg

    def test_get_not_found(self):
        router = MessageRouter()
        assert router.get("nonexistent") is None

    def test_get_by_session(self):
        router = MessageRouter()
        m1 = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        m2 = AgentMessage(sender="c", receiver="d", message_type="report", session_id="s1")
        m3 = AgentMessage(sender="e", receiver="f", message_type="report", session_id="s2")
        router.send(m1)
        router.send(m2)
        router.send(m3)
        s1_msgs = router.get_by_session("s1")
        assert len(s1_msgs) == 2
        assert m1 in s1_msgs
        assert m2 in s1_msgs

    def test_get_by_session_empty(self):
        router = MessageRouter()
        assert router.get_by_session("nonexistent") == []

    def test_get_by_sender(self):
        router = MessageRouter()
        m1 = AgentMessage(sender="alice", receiver="bob", message_type="report", session_id="s1")
        m2 = AgentMessage(sender="alice", receiver="eve", message_type="report", session_id="s2")
        m3 = AgentMessage(sender="bob", receiver="alice", message_type="report", session_id="s1")
        router.send(m1)
        router.send(m2)
        router.send(m3)
        alice_msgs = router.get_by_sender("alice")
        assert len(alice_msgs) == 2
        assert m1 in alice_msgs
        assert m2 in alice_msgs

    def test_get_by_sender_empty(self):
        router = MessageRouter()
        assert router.get_by_sender("nobody") == []

    def test_clear_session(self):
        router = MessageRouter()
        m1 = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        m2 = AgentMessage(sender="c", receiver="d", message_type="report", session_id="s2")
        mid1 = router.send(m1)
        mid2 = router.send(m2)
        router.clear_session("s1")
        assert router.get(mid1) is None
        assert router.get(mid2) is m2  # s2 的消息保留

    def test_clear_session_twice(self):
        router = MessageRouter()
        msg = AgentMessage(sender="a", receiver="b", message_type="report", session_id="s1")
        router.send(msg)
        router.clear_session("s1")
        router.clear_session("s1")  # 第二次不应抛异常
        assert router.get_by_session("s1") == []

    def test_multiple_sessions_independent(self):
        router = MessageRouter()
        for sid in ["s1", "s2", "s3"]:
            for i in range(3):
                router.send(AgentMessage(
                    sender=f"agent_{i}", receiver="orchestrator",
                    message_type="report", session_id=sid,
                ))
        assert len(router.get_by_session("s1")) == 3
        assert len(router.get_by_session("s2")) == 3
        assert len(router.get_by_session("s3")) == 3
        assert len(router.get_by_sender("agent_0")) == 3  # 跨 session

    def test_message_router_global_singleton(self):
        from src.core.protocol import message_router
        assert isinstance(message_router, MessageRouter)
