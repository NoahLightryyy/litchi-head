"""教育小智 Agent —— 金融知识问答助手

使用 KnowledgeBase 进行语义检索，结合 LLM 生成通俗易懂的金融知识回答。
依赖链：LLM（src/utils/llm.py）✅ + KnowledgeBase（src/memory/knowledge_base.py）✅
= 第一个可对话的 Agent。

用法：
    agent = XiaoZhiAgent()
    ctx = AgentContext(session_id="s1", input_data={"question": "什么是安全边际？"})
    result = await agent.run(ctx)
"""

from typing import Any

from src.agents.base import AgentContext, AgentResult, BaseAgent
from src.memory.knowledge_base import DEFAULT_BASE_PATH, KnowledgeBase
from src.utils.llm import llm_service


class XiaoZhiAgent(BaseAgent):
    """教育小智 Agent：RAG 驱动的金融知识问答助手

    工作流程：
        1. 接收用户问题
        2. KnowledgeBase 语义检索 top-3 相关知识
        3. 知识上下文 + 系统 prompt → LLM
        4. 返回结构化回答

    Attributes:
        knowledge_base: 已初始化的 KnowledgeBase 实例
    """

    def __init__(
        self,
        name: str = "xiao_zhi",
        config: dict | None = None,
        knowledge_base_path: str = DEFAULT_BASE_PATH,
    ):
        super().__init__(name, config)
        self.knowledge_base = KnowledgeBase(base_path=knowledge_base_path)
        self.knowledge_base.load()

    def get_tools(self) -> list[Any]:
        """预留工具箱挂载点（ADR-009），Phase 1 接入具体 Tool"""
        return []

    def get_system_prompt(self) -> str:
        """教育小智的系统提示词"""
        return """你是一名专业的金融知识教育助手，名叫"小智"。
你的职责是用通俗易懂的语言解释金融概念、指标和投资知识。

核心原则：
1. 优先使用知识库中检索到的内容回答，确保准确性
2. 用通俗语言解释复杂概念，多用比喻和实例
3. 如果知识库没有相关内容，用你的知识回答，但需标注"基于我的理解"
4. 提示风险和局限性，避免给出具体的买卖建议
5. 区分事实和观点，对不确定的内容明确说明"""

    async def run(self, ctx: AgentContext) -> AgentResult:
        """执行一次金融知识问答

        Args:
            ctx: AgentContext，需包含 input_data["question"]

        Returns:
            AgentResult，data 中含 answer（回答文本）和 knowledge_sources（知识来源列表）
        """
        question = ctx.input_data.get("question", "").strip()
        if not question:
            return AgentResult(
                success=False,
                error="缺少问题（question），请提供你想了解的金融知识问题",
            )

        # ── 1. 知识库语义检索 ─────────────────────────────
        knowledge_results = self.knowledge_base.search(question, k=3)
        has_knowledge = len(knowledge_results) > 0

        # ── 2. 构造 prompt ────────────────────────────────
        if has_knowledge:
            context = "\n\n".join(
                [
                    f"【来源：{r['source']} - {r['section']}】\n{r['text'][:500]}"
                    for r in knowledge_results
                ]
            )
            prompt = (
                f"用户问题：{question}\n\n"
                f"以下是从知识库中检索到的相关内容：\n{context}\n\n"
                "请基于以上知识回答用户的问题。"
                "如果检索到的内容不足以完整回答，可以补充你自己的理解。"
            )
        else:
            prompt = (
                f"用户问题：{question}\n\n"
                "注意：知识库中没有找到直接相关的资料，请基于你的金融知识回答。"
                "如果对某些内容不确定，请明确说明。"
            )

        # ── 3. LLM 调用 ───────────────────────────────────
        system_prompt = self.get_system_prompt()
        try:
            answer = await llm_service.ainvoke(
                prompt=prompt,
                system_prompt=system_prompt,
                agent_name=self.name,
                session_id=ctx.session_id,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"LLM 调用失败: {e}",
                confidence=0.0,
            )

        # ── 4. 组装结果 ───────────────────────────────────
        confidence = 0.6 + (0.3 if has_knowledge else 0.0)
        return AgentResult(
            data={
                "answer": answer,
                "knowledge_sources": (
                    [r["source"] for r in knowledge_results] if has_knowledge else []
                ),
            },
            confidence=min(confidence, 0.95),
            reasoning=(
                f"知识检索{'命中' if has_knowledge else '未命中'}，"
                f"共 {len(knowledge_results)} 条相关结果"
            ),
        )
