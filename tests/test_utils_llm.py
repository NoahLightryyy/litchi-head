"""LLM 封装层业务测试（TD-004 追认）

注意：所有测试避免真实网络调用，使用 patch 隔离外部依赖。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.llm import LLMService, _build_llm, _record_usage


class TestBuildLLM:
    def test_invalid_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="不支持的 LLM provider"):
            _build_llm("unknown_provider")

    def test_deepseek_no_key_raises(self):
        with patch("src.utils.llm.settings") as mock_settings:
            mock_settings.llm_provider = "deepseek"
            mock_settings.deepseek_api_key = ""
            with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
                _build_llm("deepseek")

    def test_openai_no_key_raises(self):
        with patch("src.utils.llm.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.openai_api_key = ""
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                _build_llm("openai")


class TestRecordUsage:
    def test_record_with_metadata(self):
        mock_llm = MagicMock()
        mock_llm.model = "deepseek-chat"
        mock_response = MagicMock()
        mock_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }
        }

        with patch("src.utils.llm.cost_tracker") as mock_ct:
            _record_usage(mock_llm, mock_response, "test_agent", "s1")
            mock_ct.record.assert_called_once_with(
                model="deepseek-chat",
                prompt_tokens=100,
                completion_tokens=50,
                agent="test_agent",
                session_id="s1",
            )

    def test_record_without_metadata_uses_zero(self):
        mock_llm = MagicMock()
        mock_llm.model = "deepseek-chat"
        mock_response = MagicMock()
        mock_response.response_metadata = {}

        with patch("src.utils.llm.cost_tracker") as mock_ct:
            _record_usage(mock_llm, mock_response, "agent", "s1")
            mock_ct.record.assert_called_once()
            assert mock_ct.record.call_args[1]["prompt_tokens"] == 0
            assert mock_ct.record.call_args[1]["completion_tokens"] == 0

    def test_record_with_explicit_tokens(self):
        mock_llm = MagicMock()
        mock_llm.model = "deepseek-chat"
        mock_response = MagicMock()

        with patch("src.utils.llm.cost_tracker") as mock_ct:
            _record_usage(
                mock_llm, mock_response, "agent", "s1",
                prompt_tokens=200, completion_tokens=100,
            )
            mock_ct.record.assert_called_once_with(
                model="deepseek-chat",
                prompt_tokens=200,
                completion_tokens=100,
                agent="agent",
                session_id="s1",
            )


class TestLLMService:
    def test_init_empty_cache(self):
        svc = LLMService()
        assert svc._instances == {}

    def test_clear_cache(self):
        svc = LLMService()
        svc._instances["deepseek"] = MagicMock()
        svc.clear_cache()
        assert svc._instances == {}

    def test_get_llm_caches_instance(self):
        svc = LLMService()
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"

        with patch("src.utils.llm._build_llm") as mock_build:
            mock_build.return_value = MagicMock()

            llm1 = svc.get_llm("deepseek")
            llm2 = svc.get_llm("deepseek")

            assert llm1 is llm2
            mock_build.assert_called_once_with("deepseek")

    def test_get_llm_default_provider(self):
        svc = LLMService()
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"

        with patch("src.utils.llm._build_llm") as mock_build:
            mock_build.return_value = MagicMock()
            svc.get_llm()  # 无参数，应使用默认 provider
            mock_build.assert_called_once_with("deepseek")

    @pytest.mark.asyncio
    async def test_invoke_structured_raises_value_error_on_failure(self):
        svc = LLMService()
        mock_llm = MagicMock()
        structured = AsyncMock()
        structured.ainvoke.side_effect = ConnectionError("API timeout")
        mock_llm.with_structured_output.return_value = structured
        svc._instances["deepseek"] = mock_llm

        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"

        from pydantic import BaseModel

        class DummyModel(BaseModel):
            x: str

        with pytest.raises(ValueError, match="LLM 结构化输出解析失败"):
            await svc.invoke_structured(
                prompt="test",
                output_model=DummyModel,
            )

    @pytest.mark.asyncio
    async def test_invoke_structured_type_mismatch(self):
        svc = LLMService()
        mock_llm = MagicMock()
        structured = AsyncMock()
        structured.ainvoke.return_value = {"not": "a model"}
        mock_llm.with_structured_output.return_value = structured
        svc._instances["deepseek"] = mock_llm

        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"

        from pydantic import BaseModel

        class DummyModel(BaseModel):
            x: str

        with pytest.raises(ValueError, match="返回类型不匹配"):
            await svc.invoke_structured(
                prompt="test",
                output_model=DummyModel,
                agent_name="test",
            )
