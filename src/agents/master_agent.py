"""MasterAgent —— 通用大师 Agent

接收 MasterSkill 插件盘 + KnowledgeBase + LLM，模拟投资大师的人格进行问答。

职责链：
    SkillDisk（人格定义）→ MasterAgent（通用执行器）
    → KnowledgeBase（知识检索）→ LLM（结构化分析输出）

用法：
    # 方式 1：直接传入 skill
    skill = MasterSkill(skill_id="buffett", name="巴菲特", system_prompt="...")
    agent = MasterAgent(skill=skill)
    result = await agent.run(ctx)

    # 方式 2：通过 skill_id 自动加载
    agent = MasterAgent(skill_id="buffett")
    result = await agent.run(ctx)

    # 方式 3：指定 disk + skill_id
    disk = SkillDisk()
    agent = MasterAgent(skill_id="munger", disk=disk)
    result = await agent.run(ctx)
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from src.agents.base import AgentContext, AgentResult, BaseAgent
from src.memory.knowledge_base import DEFAULT_BASE_PATH, KnowledgeBase
from src.memory.skill_disk import MasterSkill, SkillDisk
from src.utils.llm import llm_service


class InvestmentAnalysis(BaseModel):
    """投资大师结构化分析输出

    由 LLM 通过 invoke_structured 生成，包含评级、评分、证据链、强制方向判断。
    direction 字段要求大师必须给出明确的 Bullish/Bearish/Neutral 方向判断，
    不可留空或输出其他值。Neutral 必须在分析中说明理由。
    """

    rating: str = Field(description="投资评级：看涨 / 看跌 / 中性 / 谨慎 / 观望")
    score: int = Field(description="信心评分（1-100）", ge=1, le=100)
    summary: str = Field(description="一句话核心观点（不超过 60 字）")
    analysis: str = Field(description="详细分析（含逻辑推理和市场逻辑）")
    key_evidence: list[str] = Field(description="关键证据或支撑逻辑列表（3-5 条）")
    risk_warning: str | None = Field(default=None, description="风险提示（可选）")
    direction: str = Field(
        default="Neutral",
        pattern=r"^(Bullish|Bearish|Neutral)$",
        description=(
            "强制输出方向判断：Bullish（看涨）/ Bearish（看跌）"
            "/ Neutral（中性）。Neutral 必须在分析中说明理由"
        ),
    )


class MasterAgent(BaseAgent):
    """通用大师 Agent：以投资大师的人格 + 知识库 + LLM 生成回答

    工作流程：
        1. 接收用户问题
        2. KnowledgeBase 语义检索（使用 skill 的 knowledge_filter 过滤）
        3. skill 的 system_prompt + 知识上下文 + 问题 → LLM
        4. 返回结构化回答

    Attributes:
        skill: 当前加载的大师 Skill（人格定义）
        knowledge_base: 已初始化的 KnowledgeBase 实例
    """

    def __init__(
        self,
        name: str = "master",
        config: dict | None = None,
        skill: MasterSkill | None = None,
        skill_id: str | None = None,
        disk: SkillDisk | None = None,
        knowledge_base_path: str = DEFAULT_BASE_PATH,
    ):
        """初始化 MasterAgent

        Args:
            skill: 直接传入 MasterSkill 实例
            skill_id: 从 SkillDisk 按 ID 加载 skill（和 skill 二选一）
            disk: 自定义 SkillDisk 实例（仅 skill_id 模式生效）
            knowledge_base_path: 知识库路径

        Raises:
            ValueError: 未提供 skill 或 skill_id
            KeyError: skill_id 在 disk 中不存在
        """
        super().__init__(name, config)

        # 解析 skill
        if skill is not None:
            self.skill = skill
        elif skill_id is not None:
            disk = disk or SkillDisk()
            self.skill = disk.load(skill_id)
            # 用 skill_id 更新 agent name
            self.name = f"master.{skill_id}"
        else:
            msg = "必须提供 skill（MasterSkill）或 skill_id（从 SkillDisk 加载）"
            raise ValueError(msg)

        self.knowledge_base = KnowledgeBase(base_path=knowledge_base_path)
        self.knowledge_base.load()

    # ── 公共方法 ──────────────────────────────

    def get_tools(self) -> list[Any]:
        """预留工具箱挂载点（ADR-009），Phase 1 接入具体 Tool"""
        return []

    def get_system_prompt(self) -> str:
        """返回当前大师的系统提示词"""
        return self.skill.system_prompt

    async def run(self, ctx: AgentContext) -> AgentResult:
        """执行一次大师问答

        Args:
            ctx: AgentContext，需包含 input_data["question"]

        Returns:
            AgentResult，data 中含：
                - answer: 回答文本
                - skill_id: 大师 ID
                - skill_name: 大师名称
                - knowledge_sources: 知识来源列表
        """
        question = ctx.input_data.get("question", "").strip()
        if not question:
            return AgentResult(
                success=False,
                error="缺少问题（question），请提供你想咨询的投资问题",
            )

        # ── 1. 知识库语义检索 ─────────────────────────────
        # knowledge_filter 是文本标签（如"巴菲特"），Phase 1 将支持文本级过滤
        # 当前 KB 按语义检索，已能匹配相关内容
        knowledge_results = self.knowledge_base.search(
            query=question,
            k=3,
            knowledge_type=None,
            min_score=0.0,
        )
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
                "请以你的身份和风格回答用户的问题。"
                "如果检索到的内容不足以完整回答，可以补充你自己的见解。"
            )
        else:
            prompt = (
                f"用户问题：{question}\n\n"
                "注意：知识库中没有找到直接相关的资料。"
                "请以你的身份和风格，基于你的知识回答。"
                "如果对某些内容不确定，请坦诚说明。"
            )

        # ── 3. 方向约束注入（D2：强制输出方向判断）────────────
        prompt += (
            "\n\n【强制方向判断】你必须在回答末尾的 direction 字段中明确输出：\n"
            "- Bullish —— 看涨，认为该股票有上行空间\n"
            "- Bearish —— 看跌，认为该股票有下行风险\n"
            "- Neutral —— 中性，无明显方向偏好\n"
            "若选择 Neutral（中性），必须在分析正文中说明保持中立的理由。"
        )

        # ── 4. LLM 结构化调用 ──────────────────────────────
        system_prompt = self.get_system_prompt()
        raw_analysis = await llm_service.invoke_structured(
            prompt=prompt,
            output_model=InvestmentAnalysis,
            system_prompt=system_prompt,
            agent_name=self.name,
            session_id=ctx.session_id,
        )
        analysis = cast(InvestmentAnalysis, raw_analysis)

        # ── 4. 组装结果 ───────────────────────────────────
        # 方向验证
        if analysis.direction not in ("Bullish", "Bearish", "Neutral"):
            analysis.direction = "Neutral"

        # 向后兼容：answer 保留为文本摘要+分析
        answer_text = f"{analysis.summary}\n\n{analysis.analysis}"
        if analysis.risk_warning:
            answer_text += f"\n\n⚠️ 风险提示：{analysis.risk_warning}"

        # 置信度：知识命中 + LLM 自身评分加权
        knowledge_confidence = 0.3 if has_knowledge else 0.0
        llm_confidence = analysis.score / 100
        confidence = min(0.6 + knowledge_confidence * 0.5 + llm_confidence * 0.3, 0.95)

        return AgentResult(
            data={
                "answer": answer_text,
                "skill_id": self.skill.skill_id,
                "skill_name": self.skill.name,
                "knowledge_sources": (
                    [r["source"] for r in knowledge_results] if has_knowledge else []
                ),
                # 结构化字段
                "analysis": {
                **analysis.model_dump(),
                "direction": analysis.direction,
            },
        },
            confidence=confidence,
            reasoning=(
                f"大师 [{self.skill.name}] "
                f"知识检索{'命中' if has_knowledge else '未命中'}，"
                f"共 {len(knowledge_results)} 条相关结果，"
                f"LLM 评级: {analysis.rating} (评分: {analysis.score})"
            ),
        )
