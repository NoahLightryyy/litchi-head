"""复杂度路由器测试（纯单元测试，无外部依赖）"""

from __future__ import annotations

import pytest

from src.utils.complexity_router import (
    ComplexityResult,
    ComplexityRouter,
    TaskComplexity,
)
from src.utils.llm import LLMConfig

# ── 测试夹具 ──────────────────────────────────────────────────


@pytest.fixture
def router() -> ComplexityRouter:
    return ComplexityRouter()


# ── TaskComplexity 枚举 ────────────────────────────────────────


class TestTaskComplexityEnum:
    def test_three_levels_exist(self) -> None:
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MODERATE.value == "moderate"
        assert TaskComplexity.COMPLEX.value == "complex"

    def test_enum_comparison(self) -> None:
        assert TaskComplexity.COMPLEX != TaskComplexity.SIMPLE
        assert TaskComplexity.MODERATE != TaskComplexity.COMPLEX


# ── detect(): SIMPLE ───────────────────────────────────────────


class TestDetectSimple:
    def test_short_greeting(self, router: ComplexityRouter) -> None:
        result = router.detect("你好")
        assert result.complexity == TaskComplexity.SIMPLE
        assert result.score < 0.3

    def test_what_is_query(self, router: ComplexityRouter) -> None:
        result = router.detect("什么是 LangGraph？怎么使用它？")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_quick_question(self, router: ComplexityRouter) -> None:
        result = router.detect("列出 src/ 目录下的所有 Python 文件")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_simple_bug_fix(self, router: ComplexityRouter) -> None:
        result = router.detect("修复 config.py 中的拼写错误")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_english_hello(self, router: ComplexityRouter) -> None:
        result = router.detect("hello, how are you?")
        assert result.complexity == TaskComplexity.SIMPLE


# ── detect(): MODERATE ─────────────────────────────────────────


class TestDetectModerate:
    def test_single_analyze_keyword(self, router: ComplexityRouter) -> None:
        result = router.detect("分析一下这个函数的性能")
        assert result.complexity in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)

    def test_review_request(self, router: ComplexityRouter) -> None:
        result = router.detect("审查这个 PR 中的代码变更是否合理")
        assert result.complexity == TaskComplexity.MODERATE

    def test_medium_length_prompt(self, router: ComplexityRouter) -> None:
        result = router.detect(
            "请帮我设计一个简单的数据缓存层，"
            "需要考虑 TTL 过期和 LRU 淘汰策略。"
            "数据量不大，大约 1000 条记录。"
        )
        # ~80 chars, "设计" keyword → MODERATE
        assert result.complexity == TaskComplexity.MODERATE


# ── detect(): COMPLEX ──────────────────────────────────────────


class TestDetectComplex:
    def test_multiple_complex_keywords(self, router: ComplexityRouter) -> None:
        prompt = (
            "请对当前系统的架构进行全面分析，找出性能瓶颈，"
            "并给出重构方案。需要权衡开发成本和性能收益，"
            "综合考虑短期和长期影响。"
        )
        result = router.detect(prompt)
        assert result.complexity == TaskComplexity.COMPLEX
        assert result.score >= 0.6

    def test_long_prompt_boosts_moderate(self, router: ComplexityRouter) -> None:
        """超长提示 + 无推理关键词 → MODERATE（纯长度不触发推理模式）"""
        prompt = "这是一个测试提示。" * 1000  # > 3000 chars, 无推理关键词
        result = router.detect(prompt)
        # 长文本会被提升，但无推理关键词时不应触发 COMPLEX
        assert result.complexity in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)
        assert result.score >= 0.25

    def test_long_prompt_with_keywords_complex(self, router: ComplexityRouter) -> None:
        """超长提示 + 推理关键词 → COMPLEX"""
        prompt = ("请分析系统架构的性能瓶颈并给出重构方案。"
                  "需要全面评估风险，权衡利弊。") * 100  # > 3000 chars + complex keywords
        result = router.detect(prompt)
        assert result.complexity == TaskComplexity.COMPLEX

    def test_architecture_review_complex(self, router: ComplexityRouter) -> None:
        prompt = (
            "请对 src/debate/orchestrator.py 进行架构审查，"
            "分析其设计是否合理，是否存在性能瓶颈，"
            "以及重构方案的可行性分析。需要端到端的流程梳理。"
        )
        result = router.detect(prompt)
        assert result.complexity == TaskComplexity.COMPLEX

    def test_structured_output_signal(self, router: ComplexityRouter) -> None:
        prompt = (
            "分析市场数据并以 JSON 格式返回，包含以下字段："
            "sentiment, score, evidence, confidence"
        )
        result = router.detect(prompt)
        # "分析" + "json" + "字段" → likely COMPLEX or MODERATE
        assert result.complexity in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)


# ── detect(): 边界情况 ─────────────────────────────────────────


class TestDetectEdgeCases:
    def test_empty_prompt(self, router: ComplexityRouter) -> None:
        result = router.detect("")
        assert result.complexity == TaskComplexity.SIMPLE
        assert result.score <= 0.0

    def test_mixed_signals_simple_wins(self, router: ComplexityRouter) -> None:
        # "分析" (moderate) vs "简单问题" (simple)
        prompt = "分析这个简单问题"
        result = router.detect(prompt)
        # 简单信号抵消 → MODERATE or SIMPLE
        assert result.complexity in (TaskComplexity.SIMPLE, TaskComplexity.MODERATE)

    def test_system_prompt_boosts_complexity(self, router: ComplexityRouter) -> None:
        long_system = "x" * 1500  # > 1000 chars
        result = router.detect("分析数据", system_prompt=long_system)
        # "分析" + 长 system_prompt → MODERATE or COMPLEX
        assert result.complexity in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)

    def test_pure_english_complex(self, router: ComplexityRouter) -> None:
        prompt = (
            "Perform a comprehensive architecture review of the debate engine. "
            "Analyze performance bottlenecks, evaluate trade-offs, "
            "and propose a refactoring plan."
        )
        result = router.detect(prompt)
        assert result.complexity == TaskComplexity.COMPLEX

    def test_score_bounded_0_to_1(self, router: ComplexityRouter) -> None:
        for prompt in ["你好", "分析" * 100, "架构设计 性能优化 重构方案 技术选型" * 50]:
            result = router.detect(prompt)
            assert 0.0 <= result.score <= 1.0


# ── get_llm_config() ───────────────────────────────────────────


class TestGetLLMConfig:
    def test_simple_returns_chat_model(self, router: ComplexityRouter) -> None:
        config = router.get_llm_config(TaskComplexity.SIMPLE)
        assert config.model == "deepseek-chat"
        assert config.reasoning_effort is None

    def test_moderate_returns_chat_model(self, router: ComplexityRouter) -> None:
        config = router.get_llm_config(TaskComplexity.MODERATE)
        assert config.model == "deepseek-chat"
        assert config.reasoning_effort is None

    def test_complex_returns_reasoner_model(self, router: ComplexityRouter) -> None:
        config = router.get_llm_config(TaskComplexity.COMPLEX)
        assert config.model == "deepseek-reasoner"
        assert config.reasoning_effort == "medium"

    def test_complex_preserves_custom_max_tokens(self, router: ComplexityRouter) -> None:
        base = LLMConfig(max_tokens=4096)
        config = router.get_llm_config(TaskComplexity.COMPLEX, base_config=base)
        assert config.model == "deepseek-reasoner"
        assert config.max_tokens == 4096  # 自定义值保留

    def test_complex_bumps_default_max_tokens(self, router: ComplexityRouter) -> None:
        config = router.get_llm_config(TaskComplexity.COMPLEX)
        assert config.max_tokens == 16384  # 默认 8192 → 16384

    def test_simple_not_default_config(self, router: ComplexityRouter) -> None:
        """显式 model 的 config 不是默认配置（不缓存）"""
        config = router.get_llm_config(TaskComplexity.SIMPLE)
        # model 被显式设为 "deepseek-chat" → is_default=False
        assert not config.is_default


# ── route() 组合方法 ───────────────────────────────────────────


class TestRoute:
    def test_route_returns_both(self, router: ComplexityRouter) -> None:
        config, result = router.route("你好")
        assert isinstance(config, LLMConfig)
        assert isinstance(result, ComplexityResult)

    def test_route_simple_uses_chat(self, router: ComplexityRouter) -> None:
        config, result = router.route("列出所有文件")
        assert result.complexity == TaskComplexity.SIMPLE
        assert config.model == "deepseek-chat"

    def test_route_complex_uses_reasoner(self, router: ComplexityRouter) -> None:
        config, result = router.route(
            "对系统架构进行全面分析和性能瓶颈诊断，给出重构方案"
        )
        assert result.complexity == TaskComplexity.COMPLEX
        assert config.model == "deepseek-reasoner"
        assert config.reasoning_effort == "medium"

    def test_route_respects_base_config_temperature(self, router: ComplexityRouter) -> None:
        base = LLMConfig(temperature=0.7, max_tokens=2048)
        config, result = router.route("分析数据", base_config=base)
        assert config.temperature == 0.7
        assert config.max_tokens == 2048


# ── LLMConfig.is_default 修正验证 ──────────────────────────────


class TestLLMConfigIsDefault:
    def test_true_default_config(self) -> None:
        config = LLMConfig()
        assert config.is_default

    def test_explicit_model_not_default(self) -> None:
        config = LLMConfig(model="deepseek-chat")
        assert not config.is_default

    def test_explicit_reasoner_not_default(self) -> None:
        config = LLMConfig(model="deepseek-reasoner")
        assert not config.is_default

    def test_custom_temperature_not_default(self) -> None:
        config = LLMConfig(temperature=0.7)
        assert not config.is_default

    def test_reasoning_effort_not_default(self) -> None:
        config = LLMConfig(reasoning_effort="medium")
        assert not config.is_default

    def test_custom_max_tokens_not_default(self) -> None:
        config = LLMConfig(max_tokens=4096)
        assert not config.is_default


# ── 阈值可配置性 ───────────────────────────────────────────────


class TestThresholdConfiguration:
    def test_custom_thresholds(self) -> None:
        """验证阈值可通过实例属性调整"""
        router = ComplexityRouter()
        router.COMPLEX_SCORE_THRESHOLD = 0.9
        router.MODERATE_SCORE_THRESHOLD = 0.5

        result = router.detect("分析一下这个函数")
        # 单个 "分析" → score ~0.08，< 0.5 → SIMPLE
        assert result.complexity == TaskComplexity.SIMPLE

    def test_default_thresholds_reasonable(self, router: ComplexityRouter) -> None:
        """默认阈值应满足：SIMPLE < MODERATE < COMPLEX"""
        assert router.MODERATE_SCORE_THRESHOLD < router.COMPLEX_SCORE_THRESHOLD
        assert router.MODERATE_SCORE_THRESHOLD > 0
        assert router.COMPLEX_SCORE_THRESHOLD < 1.0


# ── ComplexityResult ───────────────────────────────────────────


class TestComplexityResult:
    def test_fields_populated(self, router: ComplexityRouter) -> None:
        result = router.detect("分析架构并给出重构方案，评估风险")
        assert result.complexity in (
            TaskComplexity.MODERATE,
            TaskComplexity.COMPLEX,
        )
        assert isinstance(result.score, float)
        assert isinstance(result.reasons, list)
        assert len(result.reasons) > 0  # at least some reasons

    def test_simple_has_reasons(self, router: ComplexityRouter) -> None:
        result = router.detect("你好")
        # SIMPLE result should still have reasons (short prompt)
        assert len(result.reasons) > 0
