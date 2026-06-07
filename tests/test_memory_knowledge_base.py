"""KnowledgeBase 单元测试"""

import tempfile
from pathlib import Path

import pytest

from src.memory.knowledge_base import KnowledgeBase

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def kb_with_temp_dir():
    """创建使用临时目录的 KnowledgeBase 实例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        kb = KnowledgeBase(base_path=tmpdir)
        yield kb


@pytest.fixture
def sample_knowledge_file(tmp_path: Path) -> Path:
    """创建一个示例知识文件"""
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
    """含多个二级标题的文件"""
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


# ═══════════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeBaseInit:
    def test_init_creates_base_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "nested" / "path"
            kb = KnowledgeBase(base_path=str(base))
            assert base.exists()
            assert kb.base_path == base

    def test_init_default_path(self):
        kb = KnowledgeBase()
        assert kb.base_path == Path("data/knowledge_base")
        assert kb.chunks == []
        assert kb.embeddings is None


# ═══════════════════════════════════════════════════════════════════
# Ingest（导入知识文件）
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeBaseIngest:
    def test_ingest_adds_chunks(self, kb_with_temp_dir, sample_knowledge_file):
        kb = kb_with_temp_dir
        count = kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        assert count > 0
        assert len(kb.chunks) == count
        # 至少应该有3个chunk（三个二级标题）
        assert count >= 3

    def test_ingest_chunks_have_required_fields(self, kb_with_temp_dir, sample_knowledge_file):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        for chunk in kb.chunks:
            assert "text" in chunk
            assert "source" in chunk
            assert "type" in chunk
            assert "section" in chunk
            assert chunk["type"] == "concept"
            assert "安全边际.md" in chunk["source"]

    def test_ingest_multiple_files(
        self, kb_with_temp_dir, sample_knowledge_file, multi_section_file,
    ):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        kb.ingest(str(multi_section_file), knowledge_type="indicator")
        # 总量应该是两个文件的chunk之和
        assert len(kb.chunks) >= 5  # 3 + 3

    def test_ingest_non_existent_file(self, kb_with_temp_dir):
        kb = kb_with_temp_dir
        count = kb.ingest("non_existent.md")
        assert count == 0
        assert kb.chunks == []

    def test_ingest_empty_file(self, kb_with_temp_dir, tmp_path: Path):
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("", encoding="utf-8")
        kb = kb_with_temp_dir
        count = kb.ingest(str(empty_file))
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
# Search（语义检索）
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeBaseSearch:
    def test_search_without_ingest_returns_empty(self, kb_with_temp_dir):
        kb = kb_with_temp_dir
        results = kb.search("安全边际")
        assert results == []

    def test_search_returns_top_k(
        self, kb_with_temp_dir, sample_knowledge_file, multi_section_file,
    ):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        kb.ingest(str(multi_section_file), knowledge_type="indicator")
        results = kb.search("安全边际", k=2)
        assert len(results) <= 2

    def test_search_results_have_score(
        self, kb_with_temp_dir, sample_knowledge_file, multi_section_file,
    ):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        kb.ingest(str(multi_section_file), knowledge_type="indicator")
        results = kb.search("市盈率", k=3)
        for r in results:
            assert "text" in r
            assert "score" in r
            assert "source" in r
            assert 0 <= r["score"] <= 1.0

    def test_search_by_knowledge_type(
        self, kb_with_temp_dir, sample_knowledge_file, multi_section_file,
    ):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        kb.ingest(str(multi_section_file), knowledge_type="indicator")
        results = kb.search("PE", k=5, knowledge_type="indicator")
        for r in results:
            assert r["type"] == "indicator"

    def test_relevant_query_returns_relevant_results(self, kb_with_temp_dir, sample_knowledge_file):
        """验证语义相关性 — 安全边际查询应优先返回安全边际相关chunk"""
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        results = kb.search("安全边际 投资风险 保护", k=3)
        assert len(results) > 0
        # 第一个结果应包含"安全边际"或"风险"关键词
        top_text = results[0]["text"]
        assert "安全边际" in top_text or "风险" in top_text


# ═══════════════════════════════════════════════════════════════════
# Save / Load（持久化）
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeBasePersistence:
    def test_save_and_load(self, kb_with_temp_dir, sample_knowledge_file):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        kb.save()

        # 验证文件已创建
        assert (kb.base_path / "chunks.json").exists()

        # 新建实例加载
        kb2 = KnowledgeBase(base_path=str(kb.base_path))
        kb2.load()
        assert len(kb2.chunks) == len(kb.chunks)
        assert kb2.chunks[0]["text"] == kb.chunks[0]["text"]

    def test_load_empty_does_not_crash(self, kb_with_temp_dir):
        kb = kb_with_temp_dir
        # 没有保存过就加载，不应报错
        kb.load()  # should not raise
        assert kb.chunks == []

    def test_save_preserves_embeddings(self, kb_with_temp_dir, sample_knowledge_file):
        kb = kb_with_temp_dir
        kb.ingest(str(sample_knowledge_file), knowledge_type="concept")
        original_count = len(kb.chunks)
        original_embedding_shape = kb.embeddings.shape if kb.embeddings is not None else None

        kb.save()

        kb2 = KnowledgeBase(base_path=str(kb.base_path))
        kb2.load()
        assert len(kb2.chunks) == original_count
        if original_embedding_shape is not None:
            assert kb2.embeddings is not None
            assert kb2.embeddings.shape == original_embedding_shape
