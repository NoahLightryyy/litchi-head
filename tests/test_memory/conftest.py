"""pytest 共享配置 —— memory 模块测试基座

提供：
1. KnowledgeBase 测试 fixture（kb_with_temp_dir）
2. 知识文件 fixture（sample_knowledge_file / multi_section_file）
3. 根 conftest.py 中的共享 fixture 自动继承

用法：
    def test_ingest(kb_with_temp_dir, sample_knowledge_file):
        kb = kb_with_temp_dir
        count = kb.ingest(str(sample_knowledge_file))
        assert count > 0
"""

from pathlib import Path

import pytest

from src.memory.knowledge_base import KnowledgeBase


@pytest.fixture
def kb_with_temp_dir():
    """创建使用临时目录的 KnowledgeBase 实例"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        kb = KnowledgeBase(base_path=tmpdir)
        yield kb


@pytest.fixture
def sample_knowledge_file(tmp_path: Path) -> Path:
    """创建一个示例知识文件（安全边际相关）"""
    content = """# 安全边际

安全边际（Margin of Safety）是价值投资的核心概念，
由本杰明·格雷厄姆提出。

## 定义

安全边际 = 内在价值 - 市场价格
当市场价格低于内在价值时，就有了安全边际。

## 重要性

安全边际越大，投资风险越低。
它是在估值错误或市场波动时的保护垫。

## 如何计算

对于股票投资：
1. 估算公司的内在价值（DCF、PE 估值等）
2. 与当前市场价格比较
3. 差值越大，安全边际越大
"""
    file_path = tmp_path / "安全边际.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def multi_section_file(tmp_path: Path) -> Path:
    """含多个二级标题的文件（PE 相关）"""
    content = """# PE（市盈率）

市盈率是股票估值最常用的指标之一。

## PE 定义

PE = Price / Earnings Per Share
市盈率 = 股价 / 每股收益

## PE 类型

- 静态PE：使用上一年度净利润
- 滚动PE（TTM）：使用最近四个季度净利润
- 动态PE：使用预测净利润

## PE 的用法

低PE可能表示股票被低估，高PE可能表示被高估。
但不同行业PE差异很大，需横向对比。
"""
    file_path = tmp_path / "PE.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path
