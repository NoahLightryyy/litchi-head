"""VCR 录制/回放配置

用于录制真实的 LLM API 响应，在后续测试中回放：
- 第 1 次运行：真实调用 LLM，录制响应到 tests/cassettes/
- 后续运行：使用录制的响应，不实际调用 API

用法：
    from tests.vcr_config import my_vcr

    @my_vcr.use_cassette("news_analysis.yaml")
    async def test_with_vcr():
        ...

前提：
    pip install pytest-vcr  （已在 pyproject.toml dev 依赖中）
"""

# 从环境变量读取 cassette 目录，默认 tests/cassettes
import os

import vcr

CASSETTE_DIR = os.environ.get(
    "VCR_CASSETTE_DIR",
    os.path.join(os.path.dirname(__file__), "cassettes"),
)

my_vcr = vcr.VCR(
    cassette_library_dir=CASSETTE_DIR,
    record_mode="once",            # 第一次录制，后续回放
    match_on=["uri", "method"],    # 按请求地址和方法匹配
    filter_headers=["authorization", "Authorization"],  # 不记录 API Key
    decode_compressed_response=True,
)
