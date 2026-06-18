"""pytest 共享配置 —— utils 模块测试基座

提供：
1. （当前无模块级共享 fixture — 各测试文件独立定义）
2. 根 conftest.py 中的共享 fixture 自动继承

注意：utils 模块的两个测试文件（llm / cost_tracker）当前均使用标准
pytest fixture（tmp_path / monkeypatch / mocker），无需额外共享 fixture。
此文件主要建立目录级 conftest 模式，便于后续添加共享 fixture。
"""

# Fixtures 可在此添加，例如：
#
# @pytest.fixture
# def temp_log_dir(tmp_path):
#     """临时日志目录"""
#     return str(tmp_path / "logs")
