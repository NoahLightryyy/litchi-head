"""LLM 封装层业务测试（TD-004 追认）

注意：所有测试避免真实网络调用，使用 patch 隔离外部依赖。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.llm import LLMConfig, LLMService, _build_llm, _record_usage


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
            mock_build.assert_called_once_with("deepseek", None)

    def test_get_llm_default_provider(self):
        svc = LLMService()
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"

        with patch("src.utils.llm._build_llm") as mock_build:
            mock_build.return_value = MagicMock()
            svc.get_llm()  # 无参数，应使用默认 provider
            mock_build.assert_called_once_with("deepseek", None)

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


class TestLLMConfig:
    """LLMConfig 数据类测试（TD-012）"""

    def test_default_values_match_hardcoded(self):
        config = LLMConfig()
        assert config.temperature == 0.3
        assert config.max_tokens == 8192
        assert config.model is None
        assert config.stream is False
        assert config.reasoning_effort is None

    def test_custom_values(self):
        config = LLMConfig(temperature=0.7, max_tokens=4096, model="deepseek-reasoner")
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.model == "deepseek-reasoner"

    def test_frozen_cannot_be_mutated(self):
        config = LLMConfig(temperature=0.5)
        with pytest.raises(AttributeError):
            config.temperature = 0.9  # type: ignore[misc]

    def test_is_default_true_when_default(self):
        assert LLMConfig().is_default is True

    def test_is_default_false_when_custom_temperature(self):
        assert LLMConfig(temperature=0.7).is_default is False

    def test_is_default_false_when_custom_max_tokens(self):
        assert LLMConfig(max_tokens=4096).is_default is False


class TestBuildLLMWithConfig:
    """_build_llm 配置感知测试（TD-012）"""

    def test_build_with_default_config(self):
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
            with patch("src.utils.llm.ChatDeepSeek") as mock_ds:
                _build_llm("deepseek", LLMConfig())
                mock_ds.assert_called_once_with(
                    model="deepseek-chat", temperature=0.3,
                    model_kwargs={"max_tokens": 8192},
                )

    def test_build_with_custom_temperature(self):
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
            with patch("src.utils.llm.ChatDeepSeek") as mock_ds:
                _build_llm("deepseek", LLMConfig(temperature=0.7, max_tokens=4096))
                mock_ds.assert_called_once_with(
                    model="deepseek-chat", temperature=0.7,
                    model_kwargs={"max_tokens": 4096},
                )

    def test_build_with_model_override(self):
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
            with patch("src.utils.llm.ChatDeepSeek") as mock_ds:
                _build_llm("deepseek", LLMConfig(model="deepseek-reasoner"))
                mock_ds.assert_called_once_with(
                    model="deepseek-reasoner", temperature=0.3,
                    model_kwargs={"max_tokens": 8192},
                )

    def test_build_openai_with_config(self):
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "openai"
            mock_s.openai_api_key = "sk-test"
            with patch("src.utils.llm.ChatOpenAI") as mock_co:
                _build_llm("openai", LLMConfig(temperature=0.1))
                mock_co.assert_called_once_with(
                    model="gpt-4o-mini", temperature=0.1,
                    model_kwargs={"max_tokens": 8192},
                )

    def test_build_without_config_uses_defaults(self):
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
            with patch("src.utils.llm.ChatDeepSeek") as mock_ds:
                _build_llm("deepseek")
                mock_ds.assert_called_once_with(
                    model="deepseek-chat", temperature=0.3,
                    model_kwargs={"max_tokens": 8192},
                )


class TestLLMServiceConfigCache:
    """LLMService 配置感知缓存策略测试（TD-012 + TD-015）"""

    def test_default_config_caches_by_provider(self):
        svc = LLMService()
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
        with patch("src.utils.llm._build_llm") as mock_build:
            mock_build.return_value = MagicMock()
            llm1 = svc.get_llm("deepseek", LLMConfig())
            llm2 = svc.get_llm("deepseek", LLMConfig())
            assert llm1 is llm2
            mock_build.assert_called_once()

    def test_custom_config_does_not_cache(self):
        svc = LLMService()
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
            with patch("src.utils.llm._build_llm") as mock_build:
                mock_build.side_effect = [MagicMock(), MagicMock()]
                llm1 = svc.get_llm("deepseek", LLMConfig(temperature=0.7))
                llm2 = svc.get_llm("deepseek", LLMConfig(temperature=0.7))
                assert llm1 is not llm2
                assert mock_build.call_count == 2

    def test_no_config_caches_by_provider(self):
        """不传 config → None，旧行为按 provider 缓存"""
        svc = LLMService()
        with patch("src.utils.llm.settings") as mock_s:
            mock_s.llm_provider = "deepseek"
            mock_s.deepseek_api_key = "sk-test"
        with patch("src.utils.llm._build_llm") as mock_build:
            mock_build.return_value = MagicMock()
            llm1 = svc.get_llm("deepseek")
            llm2 = svc.get_llm("deepseek")
            assert llm1 is llm2
            mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_ainvoke_passes_config(self):
        svc = LLMService()
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = "config reply"
        mock_resp.response_metadata = {}
        mock_llm.ainvoke.return_value = mock_resp

        with patch.object(svc, "get_llm", return_value=mock_llm) as mock_get:
            result = await svc.ainvoke(
                prompt="test", agent_name="a", session_id="s",
                llm_config=LLMConfig(temperature=0.5),
            )
            assert result == "config reply"
            # provider=None 因为 ainvoke 把原始 provider（None）传给 get_llm
            mock_get.assert_called_with(None, LLMConfig(temperature=0.5))

    @pytest.mark.asyncio
    async def test_ainvoke_without_config_backward_compatible(self):
        svc = LLMService()
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = "reply"
        mock_resp.response_metadata = {}
        mock_llm.ainvoke.return_value = mock_resp

        with patch.object(svc, "get_llm", return_value=mock_llm) as mock_get:
            result = await svc.ainvoke(
                prompt="test", agent_name="a", session_id="s",
            )
            assert result == "reply"
            mock_get.assert_called_with(None, None)

    @pytest.mark.asyncio
    async def test_invoke_structured_passes_config(self):
        svc = LLMService()
        mock_llm = MagicMock()
        structured = AsyncMock()
        from pydantic import BaseModel

        class DummyOutput(BaseModel):
            x: str

        structured.ainvoke.return_value = DummyOutput(x="hello")
        mock_llm.with_structured_output.return_value = structured

        with patch.object(svc, "get_llm", return_value=mock_llm) as mock_get:
            result = await svc.invoke_structured(
                prompt="test", output_model=DummyOutput,
                agent_name="a", session_id="s",
                llm_config=LLMConfig(temperature=0.1),
            )
            assert result.x == "hello"  # type: ignore[attr-defined]
            mock_get.assert_called_with(None, LLMConfig(temperature=0.1))


class TestLLMServiceStream:
    """LLMService 流式异步调用测试（TD-013）"""

    @pytest.mark.asyncio
    async def test_astream_yields_content(self):
        """基础流式调用：逐 token 返回内容"""
        svc = LLMService()
        mock_llm = AsyncMock()

        async def _mock_astream(_messages):
            yield MagicMock(content="Hello")
            yield MagicMock(content=" World")

        mock_llm.astream = _mock_astream

        with patch("src.utils.llm._record_usage") as mock_record:
            with patch.object(svc, "get_llm", return_value=mock_llm):
                chunks = [c async for c in svc.astream(
                    prompt="test", agent_name="a", session_id="s",
                )]
                assert chunks == ["Hello", " World"]
                mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_astream_with_system_prompt(self):
        """流式调用传递 system_prompt"""
        svc = LLMService()
        mock_llm = AsyncMock()
        collected_messages = []

        async def _mock_astream(messages):
            collected_messages.extend(messages)
            yield MagicMock(content="reply")

        mock_llm.astream = _mock_astream

        with patch("src.utils.llm._record_usage"):
            with patch.object(svc, "get_llm", return_value=mock_llm):
                chunks = [c async for c in svc.astream(
                    prompt="question", system_prompt="be concise",
                )]
                assert chunks == ["reply"]
                assert len(collected_messages) == 2
                assert collected_messages[0].content == "be concise"
                assert collected_messages[1].content == "question"

    @pytest.mark.asyncio
    async def test_astream_passes_config(self):
        """astream 正确传递 llm_config 给 get_llm"""
        svc = LLMService()
        mock_llm = AsyncMock()

        async def _mock_astream(_messages):
            yield MagicMock(content="chunk")

        mock_llm.astream = _mock_astream

        with patch("src.utils.llm._record_usage"):
            with patch.object(svc, "get_llm", return_value=mock_llm) as mock_get:
                chunks = [c async for c in svc.astream(
                    prompt="test", llm_config=LLMConfig(temperature=0.7),
                )]
                assert chunks == ["chunk"]
                mock_get.assert_called_with(None, LLMConfig(temperature=0.7))

    @pytest.mark.asyncio
    async def test_astream_skips_empty_content(self):
        """跳过空内容片段"""
        svc = LLMService()
        mock_llm = AsyncMock()

        async def _mock_astream(_messages):
            yield MagicMock(content="A")

            yield MagicMock(content="")

            yield MagicMock(content="B")

        mock_llm.astream = _mock_astream

        with patch("src.utils.llm._record_usage"):
            with patch.object(svc, "get_llm", return_value=mock_llm):
                chunks = [c async for c in svc.astream(prompt="test")]
                assert chunks == ["A", "B"]

    @pytest.mark.asyncio
    async def test_astream_records_usage_with_agent_name(self):
        """指定 agent_name 时流结束后记录费用"""
        svc = LLMService()
        mock_llm = AsyncMock()

        async def _mock_astream(_messages):
            yield MagicMock(content="data")

        mock_llm.astream = _mock_astream
        mock_llm.model = "test-model"

        recorded = {}

        def _fake_record(llm, resp, agent, sid, **kwargs):
            recorded["agent"] = agent
            recorded["sid"] = sid

        with patch("src.utils.llm._record_usage", side_effect=_fake_record) as mock_record:
            with patch.object(svc, "get_llm", return_value=mock_llm):
                chunks = [c async for c in svc.astream(
                    prompt="test", agent_name="stream_agent", session_id="sess1",
                )]
                assert chunks == ["data"]
                mock_record.assert_called_once()
                assert recorded["agent"] == "stream_agent"
                assert recorded["sid"] == "sess1"

    @pytest.mark.asyncio
    async def test_astream_no_record_when_unknown(self):
        """agent_name=unknown 时跳过费用记录"""
        svc = LLMService()
        mock_llm = AsyncMock()

        async def _mock_astream(_messages):
            yield MagicMock(content="data")

        mock_llm.astream = _mock_astream

        with patch("src.utils.llm._record_usage") as mock_record:
            with patch.object(svc, "get_llm", return_value=mock_llm):
                chunks = [c async for c in svc.astream(prompt="test")]
                assert chunks == ["data"]
                mock_record.assert_not_called()
