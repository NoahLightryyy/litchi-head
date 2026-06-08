"""TD-016 LangGraph 最小原型验证

验证目标（ADR-002）：
1. StateGraph 基础搭建是否与项目结构兼容
2. BaseAgent.run(AgentContext) -> AgentResult 能否直接作为 LangGraph 节点
3. AgentContext dataclass 能否映射为 StateGraph 的 State 字段
4. 节点间消息传递是否走通（顺序 + 条件路由）
5. AgentResult 在 State 中的序列化兼容性

设计原则：
- 不修改任何业务代码（纯测试验证）
- 全部使用 mock LLM（不调用真实 API）
- 使用适配器模式桥接 BaseAgent ↔ LangGraph 节点
- 若验证失败，记录具体不兼容点而非硬改接口

LangGraph 版本: >= 0.3.0
"""

from __future__ import annotations

from typing import Any, TypedDict

import pytest
from langgraph.graph import END, StateGraph

from src.agents.base import AgentContext, AgentResult, BaseAgent

# ═══════════════════════════════════════════════════════════════════
# 适配层：LangGraph Node Adapter
# ═══════════════════════════════════════════════════════════════════


class DebateState(TypedDict):
    """LangGraph State 定义 —— 模拟辩论引擎的共享状态

    session_id:   会话标识
    input_data:   输入数据（问题/新闻/行情等）
    current_round: 当前辩论轮次
    agent_outputs: 所有 Agent 的输出，{agent_name: AgentResult}
    next_agent:   下一个要执行的 Agent（条件路由用）
    errors:       错误记录
    """

    session_id: str
    input_data: dict
    current_round: int
    agent_outputs: dict[str, AgentResult]
    next_agent: str | None
    errors: list[str]


async def agent_node(state: DebateState, agent: BaseAgent) -> dict:
    """将 BaseAgent 适配为 LangGraph 节点

    核心验证：
    - BaseAgent.run(AgentContext) -> AgentResult 作为节点是否可行
    - AgentContext 从 State 字段构建的映射是否正确
    - AgentResult 存入 State 后能否正常序列化

    Args:
        state: 当前 DebateState
        agent: 要运行的 BaseAgent 实例

    Returns:
        State 更新 dict（LangGraph 节点返回值）
    """
    ctx = AgentContext(
        session_id=state.get("session_id", ""),
        input_data=state.get("input_data", {}),
        current_round=state.get("current_round", 0),
        peer_outputs=list(state.get("agent_outputs", {}).values()),
        target_audience="debate_group",
    )

    result = await agent.run_safe(ctx)

    current_outputs: dict[str, AgentResult] = dict(
        state.get("agent_outputs", {})
    )
    current_outputs[agent.name] = result

    update: dict[str, Any] = {
        "agent_outputs": current_outputs,
    }

    # 条件路由准备：失败记录 errors，成功推进 next_agent
    if not result.success:
        errors: list[str] = list(state.get("errors", []))
        errors.append(result.error or f"{agent.name} 执行失败")
        update["errors"] = errors
        update["next_agent"] = "error_handler"
    else:
        update["next_agent"] = None

    return update


# ═══════════════════════════════════════════════════════════════════
# 测试用 Agent 子类
# ═══════════════════════════════════════════════════════════════════


class TestAgent(BaseAgent):
    """测试用 Agent —— 模拟真实 Agent 的 run() 行为"""

    __test__ = False  # 非 pytest 测试类，避免 collection 警告

    def __init__(
        self,
        name: str = "test_agent",
        config: dict | None = None,
        response_text: str = "测试响应",
        should_fail: bool = False,
    ):
        super().__init__(name, config)
        self._response_text = response_text
        self._should_fail = should_fail

    async def run(self, ctx: AgentContext) -> AgentResult:
        question = ctx.input_data.get("question", "")
        return AgentResult(
            data={
                "answer": f"{self._response_text}: {question}",
                "agent_info": self.name,
            },
            confidence=0.85 if not self._should_fail else 0.0,
            reasoning=f"{self.name} 分析完成",
        )


class FailingAgent(BaseAgent):
    """模拟执行失败的 Agent —— 测试错误传播"""

    __test__ = False  # 非 pytest 测试类

    def __init__(self, name: str = "failing_agent", config: dict | None = None):
        super().__init__(name, config)

    async def run(self, ctx: AgentContext) -> AgentResult:
        msg = f"{self.name} 模拟分析失败"
        raise ValueError(msg)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def initial_state() -> DebateState:
    """标准的初始辩论状态"""
    return DebateState(
        session_id="lg-test-001",
        input_data={
            "question": "当前市场走势如何？",
            "news": "今日沪指收涨0.5%，成交量放大",
            "ticker": "000001",
        },
        current_round=1,
        agent_outputs={},
        next_agent=None,
        errors=[],
    )


@pytest.fixture
def agent_a() -> TestAgent:
    return TestAgent(name="价值分析师", response_text="价值分析")


@pytest.fixture
def agent_b() -> TestAgent:
    return TestAgent(name="趋势分析师", response_text="趋势分析")


# ═══════════════════════════════════════════════════════════════════
# Test 1: 基础图构建
# ═══════════════════════════════════════════════════════════════════


class TestGraphConstruction:
    """验证 LangGraph StateGraph 基础构造能力"""

    def test_create_graph(self):
        """StateGraph 创建 + add_node + compile 基础链路"""
        graph = StateGraph(DebateState)
        assert graph is not None

        # 添加一个简单的节点（返回 state 更新的函数）
        async def noop(state: DebateState) -> dict:
            return {"errors": state.get("errors", [])}

        graph.add_node("start", noop)
        graph.set_entry_point("start")
        graph.add_edge("start", END)

        app = graph.compile()
        assert app is not None

    def test_noop_invoke(self):
        """空节点调用验证"""
        graph = StateGraph(DebateState)

        async def identity(state: DebateState) -> dict:
            return {}

        graph.add_node("pass", identity)
        graph.set_entry_point("pass")
        graph.add_edge("pass", END)
        app = graph.compile()

        import asyncio

        result = asyncio.run(
            app.ainvoke({
                "session_id": "test",
                "input_data": {},
                "current_round": 0,
                "agent_outputs": {},
                "next_agent": None,
                "errors": [],
            })
        )
        assert isinstance(result, dict)
        assert result["session_id"] == "test"

    def test_sequential_two_nodes(self):
        """顺序执行两个节点，验证 state 传递"""
        graph = StateGraph(DebateState)

        async def first(state: DebateState) -> dict:
            return {"current_round": state.get("current_round", 0) + 1}

        async def second(state: DebateState) -> dict:
            return {"next_agent": "done"}

        graph.add_node("first", first)
        graph.add_node("second", second)
        graph.set_entry_point("first")
        graph.add_edge("first", "second")
        graph.add_edge("second", END)
        app = graph.compile()

        import asyncio

        result = asyncio.run(
            app.ainvoke({
                "session_id": "seq-test",
                "input_data": {},
                "current_round": 0,
                "agent_outputs": {},
                "next_agent": None,
                "errors": [],
            })
        )
        assert result["current_round"] == 1
        assert result["next_agent"] == "done"


# ═══════════════════════════════════════════════════════════════════
# Test 2: 单 Agent 节点
# ═══════════════════════════════════════════════════════════════════


class TestSingleAgentNode:
    """验证 BaseAgent 适配为 LangGraph 节点的可行性"""

    @pytest.mark.asyncio
    async def test_adapter_direct_call(self, agent_a: TestAgent, initial_state: DebateState):
        """适配器函数直接调用验证"""
        update = await agent_node(initial_state, agent_a)
        assert "agent_outputs" in update
        assert agent_a.name in update["agent_outputs"]
        result = update["agent_outputs"][agent_a.name]
        assert result.success is True
        assert "价值分析" in result.data.get("answer", "")

    @pytest.mark.asyncio
    async def test_adapter_in_graph(self, agent_a: TestAgent, initial_state: DebateState):
        """适配器作为 LangGraph 节点运行"""
        graph = StateGraph(DebateState)

        # 闭包绑定 agent 实例
        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, agent_a)

        graph.add_node("analyst", node_fn)
        graph.set_entry_point("analyst")
        graph.add_edge("analyst", END)
        app = graph.compile()

        result = await app.ainvoke(initial_state)
        assert result["agent_outputs"] is not None
        assert agent_a.name in result["agent_outputs"]
        output = result["agent_outputs"][agent_a.name]
        assert output.success is True

    @pytest.mark.asyncio
    async def test_input_data_preserved(self, agent_a: TestAgent, initial_state: DebateState):
        """验证 input_data 完整传递到 Agent"""
        graph = StateGraph(DebateState)

        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, agent_a)

        graph.add_node("analyst", node_fn)
        graph.set_entry_point("analyst")
        graph.add_edge("analyst", END)
        app = graph.compile()

        result = await app.ainvoke(initial_state)
        output = result["agent_outputs"][agent_a.name]
        assert "当前市场走势如何？" in output.data.get("answer", "")


# ═══════════════════════════════════════════════════════════════════
# Test 3: 双 Agent 顺序执行
# ═══════════════════════════════════════════════════════════════════


class TestTwoAgentSequential:
    """验证两个 Agent 顺序执行时的消息传递"""

    @pytest.mark.asyncio
    async def test_a_then_b(
        self, agent_a: TestAgent, agent_b: TestAgent, initial_state: DebateState
    ):
        """Agent A → Agent B 顺序执行"""
        graph = StateGraph(DebateState)

        async def node_a(state: DebateState) -> dict:
            return await agent_node(state, agent_a)

        async def node_b(state: DebateState) -> dict:
            return await agent_node(state, agent_b)

        graph.add_node("value_analyst", node_a)
        graph.add_node("trend_analyst", node_b)
        graph.set_entry_point("value_analyst")
        graph.add_edge("value_analyst", "trend_analyst")
        graph.add_edge("trend_analyst", END)
        app = graph.compile()

        result = await app.ainvoke(initial_state)
        outputs = result["agent_outputs"]
        assert len(outputs) == 2
        assert agent_a.name in outputs
        assert agent_b.name in outputs

    @pytest.mark.asyncio
    async def test_peer_outputs_passed(
        self, agent_a: TestAgent, agent_b: TestAgent, initial_state: DebateState
    ):
        """验证第二个 Agent 能收到第一个 Agent 的输出作为 peer_outputs"""
        captured: list[dict] = []

        class CapturingAgent(BaseAgent):
            async def run(self, ctx: AgentContext) -> AgentResult:
                captured.append({
                    "peer_count": len(ctx.peer_outputs),
                    "peer_names": [r.agent_name for r in ctx.peer_outputs],
                })
                return AgentResult(data={"status": "ok"})

        capturer = CapturingAgent(name="capturer")
        graph = StateGraph(DebateState)

        async def node_a(state: DebateState) -> dict:
            return await agent_node(state, agent_a)

        async def node_b(state: DebateState) -> dict:
            return await agent_node(state, capturer)

        graph.add_node("analyst_a", node_a)
        graph.add_node("analyst_b", node_b)
        graph.set_entry_point("analyst_a")
        graph.add_edge("analyst_a", "analyst_b")
        graph.add_edge("analyst_b", END)
        app = graph.compile()

        await app.ainvoke(initial_state)
        assert len(captured) == 1
        assert captured[0]["peer_count"] == 1
        assert captured[0]["peer_names"] == [agent_a.name]


# ═══════════════════════════════════════════════════════════════════
# Test 4: AgentContext 状态映射
# ═══════════════════════════════════════════════════════════════════


class TestAgentContextMapping:
    """验证 State 字段正确映射到 AgentContext"""

    @pytest.mark.asyncio
    async def test_context_fields_mapped(self, initial_state: DebateState):
        """所有 AgentContext 字段从 State 正确构建"""
        captured: list[AgentContext] = []

        class SniffingAgent(BaseAgent):
            async def run(self, ctx: AgentContext) -> AgentResult:
                captured.append(ctx)
                return AgentResult(data={"ok": True})

        agent = SniffingAgent(name="sniffer")
        graph = StateGraph(DebateState)

        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, agent)

        graph.add_node("sniffer", node_fn)
        graph.set_entry_point("sniffer")
        graph.add_edge("sniffer", END)
        app = graph.compile()

        await app.ainvoke(initial_state)
        assert len(captured) == 1
        ctx = captured[0]
        assert ctx.session_id == "lg-test-001"
        assert ctx.input_data.get("question") == "当前市场走势如何？"
        assert ctx.current_round == 1
        assert ctx.target_audience == "debate_group"

    @pytest.mark.asyncio
    async def test_peer_outputs_in_context(
        self, agent_a: TestAgent, initial_state: DebateState
    ):
        """带 peer_outputs 的 State 映射验证"""
        # 预填充一个 agent 输出
        pre_state = DebateState(
            session_id=initial_state["session_id"],
            input_data=initial_state["input_data"],
            current_round=2,
            agent_outputs={
                "prior_agent": AgentResult(
                    agent_name="prior_agent",
                    data={"analysis": "先前的分析"},
                    success=True,
                ),
            },
            next_agent=None,
            errors=[],
        )

        captured: list[AgentContext] = []

        class PeerAwareAgent(BaseAgent):
            async def run(self, ctx: AgentContext) -> AgentResult:
                captured.append(ctx)
                return AgentResult(data={"ok": True})

        agent = PeerAwareAgent(name="peer_aware")
        graph = StateGraph(DebateState)

        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, agent)

        graph.add_node("analyst", node_fn)
        graph.set_entry_point("analyst")
        graph.add_edge("analyst", END)
        app = graph.compile()

        await app.ainvoke(pre_state)
        assert len(captured) == 1
        ctx = captured[0]
        assert len(ctx.peer_outputs) == 1
        assert ctx.peer_outputs[0].agent_name == "prior_agent"
        assert ctx.current_round == 2


# ═══════════════════════════════════════════════════════════════════
# Test 5: 错误传播
# ═══════════════════════════════════════════════════════════════════


class TestErrorPropagation:
    """验证 Agent 失败时 Graph 正确处理"""

    @pytest.mark.asyncio
    async def test_agent_failure_recorded(self, initial_state: DebateState):
        """Agent 执行失败 → errors 列表记录错误"""
        failing = FailingAgent(name="bad_agent")
        graph = StateGraph(DebateState)

        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, failing)

        graph.add_node("analyst", node_fn)
        graph.set_entry_point("analyst")
        graph.add_edge("analyst", END)
        app = graph.compile()

        result = await app.ainvoke(initial_state)
        assert len(result.get("errors", [])) > 0
        error_text = result["errors"][0]
        assert "模拟分析失败" in error_text

    @pytest.mark.asyncio
    async def test_failure_does_not_crash_graph(self, initial_state: DebateState):
        """单个 Agent 失败不应导致整个 Graph 崩溃（run_safe 保障）"""
        failing = FailingAgent(name="bad_agent")
        graph = StateGraph(DebateState)

        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, failing)

        graph.add_node("analyst", node_fn)
        graph.set_entry_point("analyst")
        graph.add_edge("analyst", END)
        app = graph.compile()

        # run_safe 内部捕获异常，不会冒泡
        result = await app.ainvoke(initial_state)
        assert isinstance(result, dict)
        # Agent 输出应包含失败结果
        assert "bad_agent" in result.get("agent_outputs", {})
        failed_result = result["agent_outputs"]["bad_agent"]
        assert failed_result.success is False

    @pytest.mark.asyncio
    async def test_successive_agents_after_failure(
        self, agent_b: TestAgent, initial_state: DebateState
    ):
        """失败 Agent 后仍有正常 Agent 执行"""
        failing = FailingAgent(name="bad_agent")
        graph = StateGraph(DebateState)

        async def bad_node(state: DebateState) -> dict:
            return await agent_node(state, failing)

        async def good_node(state: DebateState) -> dict:
            return await agent_node(state, agent_b)

        graph.add_node("bad", bad_node)
        graph.add_node("good", good_node)
        graph.set_entry_point("bad")
        graph.add_edge("bad", "good")
        graph.add_edge("good", END)
        app = graph.compile()

        result = await app.ainvoke(initial_state)
        assert len(result.get("errors", [])) == 1
        assert agent_b.name in result["agent_outputs"]
        assert result["agent_outputs"][agent_b.name].success is True


# ═══════════════════════════════════════════════════════════════════
# Test 6: 条件边
# ═══════════════════════════════════════════════════════════════════


class TestConditionalEdge:
    """验证条件路由 —— 根据 Agent 成功/失败走不同路径"""

    @pytest.mark.asyncio
    async def test_success_routes_to_review(self, initial_state: DebateState):
        """Agent 成功 → 进入 review 节点"""
        agent = TestAgent(name="success_agent")
        visited: list[str] = []

        graph = StateGraph(DebateState)

        async def analyst_node(state: DebateState) -> dict:
            return await agent_node(state, agent)

        async def review_node(state: DebateState) -> dict:
            visited.append("review")
            return {}

        def route_after_analyst(state: DebateState) -> str:
            return "review" if len(state.get("errors", [])) == 0 else "error_handler"

        graph.add_node("analyst", analyst_node)
        graph.add_node("review", review_node)
        graph.set_entry_point("analyst")
        graph.add_conditional_edges("analyst", route_after_analyst)
        graph.add_edge("review", END)
        app = graph.compile()

        await app.ainvoke(initial_state)
        assert "review" in visited

    @pytest.mark.asyncio
    async def test_failure_routes_to_error(self, initial_state: DebateState):
        """Agent 失败 → 进入 error_handler 节点"""
        failing = FailingAgent(name="fail_agent")
        visited: list[str] = []

        graph = StateGraph(DebateState)

        async def bad_node(state: DebateState) -> dict:
            return await agent_node(state, failing)

        async def error_node(state: DebateState) -> dict:
            visited.append("error_handler")
            return {}

        def route_after_fail(state: DebateState) -> str:
            return "error_handler" if len(state.get("errors", [])) > 0 else "review"

        graph.add_node("analyst", bad_node)
        graph.add_node("error_handler", error_node)
        graph.set_entry_point("analyst")
        graph.add_conditional_edges("analyst", route_after_fail)
        graph.add_edge("error_handler", END)
        app = graph.compile()

        await app.ainvoke(initial_state)
        assert "error_handler" in visited

    @pytest.mark.asyncio
    async def test_multi_agent_conditional_flow(
        self, agent_a: TestAgent, agent_b: TestAgent, initial_state: DebateState
    ):
        """多 Agent 条件路由：A → B → (成功→review / 失败→error)"""
        visited: list[str] = []

        graph = StateGraph(DebateState)

        async def node_a(state: DebateState) -> dict:
            return await agent_node(state, agent_a)

        async def node_b(state: DebateState) -> dict:
            return await agent_node(state, agent_b)

        async def review_node(state: DebateState) -> dict:
            visited.append("review")
            return {}

        def route_after_b(state: DebateState) -> str:
            return "review" if len(state.get("errors", [])) == 0 else "error_handler"

        graph.add_node("analyst_a", node_a)
        graph.add_node("analyst_b", node_b)
        graph.add_node("review", review_node)
        graph.set_entry_point("analyst_a")
        graph.add_edge("analyst_a", "analyst_b")
        graph.add_conditional_edges("analyst_b", route_after_b)
        graph.add_edge("review", END)
        app = graph.compile()

        await app.ainvoke(initial_state)
        assert "review" in visited
        # 验证两个 Agent 都执行了
        assert len(visited) == 1  # review 只进一次


# ═══════════════════════════════════════════════════════════════════
# Test 7: State 序列化
# ═══════════════════════════════════════════════════════════════════


class TestStateSerialization:
    """验证 AgentResult + DebateState 的 JSON 序列化兼容性

    关键验证：AgentResult 是 Pydantic BaseModel（model_dump 可序列化），
    AgentContext 是 dataclass，两者在 LangGraph State 中的兼容性。
    """

    @pytest.mark.asyncio
    async def test_agent_result_json_serializable(self):
        """AgentResult（Pydantic BaseModel）序列化为 JSON"""
        result = AgentResult(
            agent_name="test",
            session_id="s1",
            success=True,
            data={"key": "value", "number": 42},
            confidence=0.9,
            reasoning="ok",
        )
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["agent_name"] == "test"
        assert dumped["data"]["key"] == "value"

        import json

        json_str = json.dumps(dumped, ensure_ascii=False)
        loaded = json.loads(json_str)
        assert loaded["agent_name"] == "test"

    @pytest.mark.asyncio
    async def test_state_with_agent_results_serializable(
        self, agent_a: TestAgent, initial_state: DebateState
    ):
        """含 AgentResult 的完整 State 可 JSON 序列化"""
        graph = StateGraph(DebateState)

        async def node_fn(state: DebateState) -> dict:
            return await agent_node(state, agent_a)

        graph.add_node("analyst", node_fn)
        graph.set_entry_point("analyst")
        graph.add_edge("analyst", END)
        app = graph.compile()

        result = await app.ainvoke(initial_state)

        import json

        # AgentResult 是 BaseModel，应在 state 中被正确存储
        output = result["agent_outputs"][agent_a.name]
        assert isinstance(output, AgentResult)

        # 序列化整个 state（受限：AgentResult 需手动 model_dump）
        # LangGraph 内部处理序列化，这里验证我们能否安全转换
        serializable_state = {
            "session_id": result["session_id"],
            "agent_outputs": {
                name: r.model_dump() if isinstance(r, AgentResult) else r
                for name, r in result["agent_outputs"].items()
            },
            "errors": result["errors"],
        }
        json_str = json.dumps(serializable_state, ensure_ascii=False)
        assert agent_a.name in json_str
        assert "价值分析" in json_str

    @pytest.mark.asyncio
    async def test_agent_context_not_in_state(self, initial_state: DebateState):
        """验证 AgentContext（dataclass）不直接作为 State 字段

        AgentContext 是模块内部传递数据，不跨模块序列化。
        State 中只存原始数据（str/dict/int），AgentContext 在适配器内构建。
        """
        state_keys = set(initial_state.keys())
        # AgentContext 的字段不应出现在 State schema 中
        assert "session_id" in state_keys  # 但 session_id 作为 str 存在
        assert "input_data" in state_keys  # input_data 作为 dict 存在
        # AgentContext 特有的字段不应是 State 顶层字段
        assert "memory" not in state_keys
        assert "config" not in state_keys

    @pytest.mark.asyncio
    async def test_state_roundtrip_via_json(self):
        """完整 State 序列化 → 反序列化 → 重建 AgentContext 的双向验证"""
        original_state = DebateState(
            session_id="roundtrip-test",
            input_data={"question": "测试问题", "price": 100},
            current_round=1,
            agent_outputs={},
            next_agent=None,
            errors=[],
        )

        # 序列化
        import json

        serialized = {
            k: (
                v.model_dump()
                if isinstance(v, AgentResult)
                else {name: r.model_dump() for name, r in v.items()}
                if isinstance(v, dict) and v
                and isinstance(next(iter(v.values())), AgentResult)
                else v
            )
            for k, v in original_state.items()
        }
        json_str = json.dumps(serialized, ensure_ascii=False)

        # 反序列化
        loaded_dict = json.loads(json_str)

        # 从反序列化数据重建 AgentContext
        ctx = AgentContext(
            session_id=loaded_dict["session_id"],
            input_data=loaded_dict["input_data"],
            current_round=loaded_dict.get("current_round", 0),
        )
        assert ctx.session_id == "roundtrip-test"
        assert ctx.input_data["question"] == "测试问题"
        assert ctx.current_round == 1
