"""复杂度感知的 DeepSeek 模型路由层

在 deepseek-chat（快速，无推理）和 deepseek-reasoner（深度推理，较慢）
之间自动切换，解决「简单问题也慢」的痛点。

用法:
    from src.utils.complexity_router import ComplexityRouter, TaskComplexity

    router = ComplexityRouter()

    # 自动检测 + 返回推荐配置
    complexity = router.detect(prompt)
    config = router.get_llm_config(complexity, base_config=None)

    # 快捷方法：一步到位
    config = router.route(prompt)
    reply = await llm_service.ainvoke(prompt, llm_config=config)

决策逻辑:
    - SIMPLE（<100 字，无复杂关键词）    → deepseek-chat, temperature=0.3
    - MODERATE（中等长度，1-2 个复杂词） → deepseek-chat, temperature=0.3
    - COMPLEX（>2000 字 或 ≥3 个复杂词）→ deepseek-reasoner, reasoning_effort="medium"

启发式规则的局限性:
    关键词匹配无法 100% 准确判断任务复杂度。以下场景可能误判：
    - 包含"分析"但实际是简单查询 → 可能被高估为 MODERATE
    - 短提示但实际需要深度推理 → 可能被低估为 SIMPLE
    - 非中文/英文混合场景 → 关键词覆盖不全
    建议：关键业务调用显式传入 LLMConfig(model="deepseek-reasoner") 而非依赖自动检测。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.utils.llm import LLMConfig


class TaskComplexity(Enum):
    """任务复杂度等级"""

    SIMPLE = "simple"        # 闲聊、简单查询、单步操作
    MODERATE = "moderate"    # 中等推理、简短代码
    COMPLEX = "complex"      # 深度分析、架构设计、多步推理


# ── 复杂度关键词 ──────────────────────────────────────────────

# 命中这些词 → 倾向 COMPLEX
_COMPLEX_TRIGGERS = [
    # 中文 — 分析与诊断
    r"分析.*根", r"根因", r"深层.*原因", r"底层.*原理",
    r"架构.*分析", r"架构.*审查", r"架构.*评估",
    r"性能.*瓶颈", r"性能.*分析", r"性能.*诊断",
    r"内存.*泄漏", r"并发.*问题",
    # 中文 — 设计与重构
    r"架构设计", r"架构.*选型", r"系统设计",
    r"重构.*方案", r"重构.*计划", r"大规模.*重构",
    r"端到端.*流程", r"跨模块.*变更", r"多模块.*联动",
    # 中文 — 评估与决策
    r"方案.*对比", r"技术.*选型", r"权衡.*利弊",
    r"评估.*风险", r"影响.*分析", r"可行性.*分析",
    r"决策.*建议", r"综合.*考量", r"综合.*考虑",
    # 中文 — 复杂实现
    r"完整.*实现", r"从零.*构建",
    # 英文
    r"architecture.*review", r"system.*design",
    r"root.*cause", r"trade.?off",
    r"comprehensive.*(?:review|analysis|audit)",
    r"refactor.*plan", r"migration.*plan",
    r"performance.*bottleneck", r"deep.*analysis",
]

# 命中这些词 → 倾向 MODERATE（单个命中不触发 COMPLEX）
_MODERATE_TRIGGERS = [
    # 中文
    "分析", "设计", "重构", "优化",
    "实现", "评估", "对比", "审查",
    "为什么", "原理", "机制", "架构",
    "诊断", "排查", "权衡",
    # 英文
    "analyze", "design", "refactor", "review",
    "implement", "evaluate", "compare",
    "why", "how.*work", "explain",
    "architecture", "diagnose", "debug",
]

# 命中这些词 → 倾向 SIMPLE（降低复杂度判定）
_SIMPLE_TRIGGERS = [
    "什么是", "怎么用", "如何.*使用",
    "列出", "显示", "查询",
    "简单.*问题", "快速.*问题",
    "你好", "谢谢", "帮助",
    "what is", "how to", "list", "show",
    "hello", "thanks", "help",
    "小改动", "修.*bug", "改.*注释",
    "更新.*文档", "更新.*README",
]


# ── 复杂度检测器 ──────────────────────────────────────────────


@dataclass
class ComplexityResult:
    """复杂度检测结果"""

    complexity: TaskComplexity
    score: float           # 0.0 ~ 1.0，越高越复杂
    reasons: list[str]     # 判定依据


class ComplexityRouter:
    """复杂度感知的路由器

    基于启发式规则（非 LLM 调用）判断任务复杂度，
    返回推荐的 LLMConfig。
    """

    # 可配置阈值
    COMPLEX_SCORE_THRESHOLD: float = 0.6
    MODERATE_SCORE_THRESHOLD: float = 0.3

    # deepseek-reasoner 不支持 temperature
    REASONER_MODEL = "deepseek-reasoner"
    CHAT_MODEL = "deepseek-chat"
    DEFAULT_REASONING_EFFORT = "medium"  # low | medium | high

    def detect(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> ComplexityResult:
        """检测任务复杂度

        两阶段判定：
        1. 先看关键词（主信号），决定基础等级
        2. 再看长度和简单信号微调（辅信号）

        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词

        Returns:
            ComplexityResult 包含等级、得分、依据
        """
        text = prompt
        reasons: list[str] = []
        prompt_len = len(prompt)

        # ── 1. 关键词匹配（主信号） ──
        complex_hits = 0
        for pattern in _COMPLEX_TRIGGERS:
            if re.search(pattern, text, re.IGNORECASE):
                complex_hits += 1

        moderate_hits = 0
        for pattern in _MODERATE_TRIGGERS:
            if re.search(pattern, text, re.IGNORECASE):
                moderate_hits += 1

        simple_hits = 0
        for pattern in _SIMPLE_TRIGGERS:
            if re.search(pattern, text, re.IGNORECASE):
                simple_hits += 1

        # ── 2. 基础分数（关键词驱动） ──
        if complex_hits >= 3:
            score = 0.75
            reasons.append(f"多个复杂关键词 ({complex_hits} 个)")
        elif complex_hits >= 2:
            score = 0.65
            reasons.append(f"复杂关键词 ({complex_hits} 个)")
        elif complex_hits == 1:
            # 单个复杂关键词 + 有推理关键词辅助 → 仍为 COMPLEX
            if moderate_hits >= 1:
                score = 0.62
                reasons.append(f"复杂+推理关键词 (c={complex_hits} m={moderate_hits})")
            else:
                score = 0.40
                reasons.append(f"复杂关键词 ({complex_hits} 个)")
        elif moderate_hits >= 2:
            score = 0.35
            reasons.append(f"推理关键词 ({moderate_hits} 个)")
        elif moderate_hits == 1:
            score = 0.30  # 单个推理关键词 → 至少 MODERATE
            reasons.append(f"推理关键词 ({moderate_hits} 个)")
        else:
            score = 0.05  # 无线索，默认为简单

        # ── 3. 长度调整（辅信号） ──
        if prompt_len > 3000:
            score += 0.25
            reasons.append(f"超长提示 ({prompt_len} 字符)")
        elif prompt_len > 1500:
            score += 0.15
            reasons.append(f"长提示 ({prompt_len} 字符)")
        elif prompt_len > 500:
            score += 0.08
        elif prompt_len < 40 and moderate_hits == 0 and complex_hits == 0:
            # 仅在无推理关键词时，极短提示才是简单信号
            score -= 0.05
            reasons.append("极短提示")

        # ── 4. 简单信号调整（减法，辅信号） ──
        if simple_hits >= 3:
            score -= 0.15
            reasons.append(f"强简单信号 ({simple_hits} 个)")
        elif simple_hits >= 1 and complex_hits == 0 and moderate_hits <= 1:
            score -= 0.10
            reasons.append(f"简单信号 ({simple_hits} 个)")

        # ── 5. 结构化输出信号 ──
        _struc_pat = (
            r"(?:json|pydantic|structured.*output|字段.*定义|结构化.*输出)"
        )
        if re.search(_struc_pat, text, re.IGNORECASE):
            score += 0.08
            reasons.append("结构化输出要求")

        # ── 6. 系统提示词信号 ──
        if system_prompt and len(system_prompt) > 1000:
            score += 0.08
            reasons.append("长系统提示词")

        # ── 7. 判定等级 ──
        score = max(0.0, min(1.0, score))

        if score >= self.COMPLEX_SCORE_THRESHOLD:
            complexity = TaskComplexity.COMPLEX
        elif score >= self.MODERATE_SCORE_THRESHOLD:
            complexity = TaskComplexity.MODERATE
        else:
            complexity = TaskComplexity.SIMPLE

        return ComplexityResult(
            complexity=complexity,
            score=score,
            reasons=reasons,
        )

    def get_llm_config(
        self,
        complexity: TaskComplexity,
        base_config: LLMConfig | None = None,
    ) -> LLMConfig:
        """根据复杂度返回推荐的 LLMConfig

        Args:
            complexity: 任务复杂度等级
            base_config: 基础配置（temperature 等），会与路由推荐合并

        Returns:
            推荐的 LLMConfig
        """
        base = base_config or LLMConfig()

        if complexity == TaskComplexity.COMPLEX:
            # deepseek-reasoner：深度推理模式
            # 注意：reasoner 不支持 temperature，使用默认即可
            return LLMConfig(
                temperature=base.temperature,  # reasoner 会忽略
                max_tokens=base.max_tokens if base.max_tokens != 8192 else 16384,
                model=self.REASONER_MODEL,
                stream=base.stream,
                reasoning_effort=self.DEFAULT_REASONING_EFFORT,
            )
        else:
            # deepseek-chat：快速模式
            return LLMConfig(
                temperature=base.temperature,
                max_tokens=base.max_tokens,
                model=self.CHAT_MODEL,
                stream=base.stream,
                reasoning_effort=None,  # chat 模型不需要
            )

    def route(
        self,
        prompt: str,
        system_prompt: str | None = None,
        base_config: LLMConfig | None = None,
    ) -> tuple[LLMConfig, ComplexityResult]:
        """一步完成检测 + 配置生成

        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词
            base_config: 基础 LLM 配置

        Returns:
            (推荐的 LLMConfig, 复杂度检测结果)
        """
        result = self.detect(prompt, system_prompt)
        config = self.get_llm_config(result.complexity, base_config)
        return config, result


# ── 全局单例 ──────────────────────────────────────────────────

complexity_router = ComplexityRouter()
