"""KnowledgeBase —— 金融知识库（RAG 语义检索核心）

基于 numpy 的轻量语义搜索，不依赖外部 embedding 模型。
后续可无缝升级为 FAISS + BGE-small-zh（见 docs/金融知识检索架构-RAG+GREP双轨方案.md）。

用法：
    kb = KnowledgeBase()
    kb.ingest("data/knowledge_base/concepts/安全边际.md", "concept")
    results = kb.search("什么是安全边际？", k=3)
"""

import json
import re
from pathlib import Path

import numpy as np

# ──────────────────────────────────────────────
# 默认配置
# ──────────────────────────────────────────────

DEFAULT_BASE_PATH = "data/knowledge_base"

# n-gram 特征提取参数
NGRAM_MIN = 2
NGRAM_MAX = 4
MAX_VOCAB_SIZE = 5000
MAX_CHUNK_CHARS = 1500


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────


def _extract_ngrams(text: str, n_min: int = NGRAM_MIN, n_max: int = NGRAM_MAX) -> list[str]:
    """从文本中提取字符 n-gram 作为特征"""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)  # 合并空白
    ngrams = []
    for n in range(n_min, n_max + 1):
        for i in range(len(text) - n + 1):
            ngrams.append(text[i : i + n])
    return ngrams


def _build_vocab(chunks: list[dict], max_size: int = MAX_VOCAB_SIZE) -> dict[str, int]:
    """从所有 chunk 文本中构建 n-gram 词表（按频率取 top-k）"""
    counter: dict[str, int] = {}
    for chunk in chunks:
        for ng in _extract_ngrams(chunk["text"]):
            counter[ng] = counter.get(ng, 0) + 1
    # 按频率降序取 top
    sorted_ngrams = sorted(counter.items(), key=lambda x: -x[1])
    return {ng: idx for idx, (ng, _) in enumerate(sorted_ngrams[:max_size])}


def _text_to_vector(text: str, vocab: dict[str, int]) -> np.ndarray:
    """将文本编码为 TF 向量"""
    vec = np.zeros(len(vocab), dtype=np.float32)
    for ng in _extract_ngrams(text):
        if ng in vocab:
            vec[vocab[ng]] += 1.0
    # L2 归一化
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def _chunk_markdown(text: str, source: str) -> list[dict]:
    """将 Markdown 文件按二级标题 (##) 分块

    每块包含：
        - text: 标题 + 正文
        - source: 源文件名
        - section: 二级标题名
    """
    doc_title = ""
    # 提取一级标题（第一个 # 开头的行）
    for line in text.split("\n"):
        line_stripped = line.strip()
        if line_stripped.startswith("# ") and not line_stripped.startswith("## "):
            doc_title = line_stripped.lstrip("# ").strip()
            break

    chunks = []
    current_section = "概述"
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            # 保存上一个 chunk
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    text = (
                        f"# {doc_title} > ## {current_section}\n{body}"
                        if doc_title else body
                    )
                    chunks.append({"text": text,
                        "source": source,
                        "section": current_section,
                        "type": "general",
                    })
            current_section = stripped.lstrip("## ").strip()
            current_lines = []
        elif stripped and not stripped.startswith("# "):
            current_lines.append(line)

    # 最后一块
    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append({
                "text": f"# {doc_title} > ## {current_section}\n{body}" if doc_title else body,
                "source": source,
                "section": current_section,
                "type": "general",
            })

    return chunks


# ──────────────────────────────────────────────
# KnowledgeBase 类
# ──────────────────────────────────────────────


class KnowledgeBase:
    """金融文本知识库 —— 基于 n-gram TF 向量的轻量语义检索

    支持导入知识文件、语义搜索、持久化保存/加载。
    Phase 1 将升级为 FAISS + BGE-small-zh。
    """

    def __init__(self, base_path: str = DEFAULT_BASE_PATH):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.chunks: list[dict] = []
        """知识块列表，每个 chunk 包含 text / source / section / type"""

        self.embeddings: np.ndarray | None = None
        """所有 chunk 的 TF 向量矩阵，shape=(n_chunks, vocab_size)"""

        self.vocab: dict[str, int] = {}
        """n-gram → index 的映射表"""

        self._dirty: bool = False
        """是否有未保存的变更"""

    # ── 导入知识 ──────────────────────────────

    def ingest(self, file_path: str, knowledge_type: str = "general") -> int:
        """导入一个知识文件（.md），返回导入的 chunk 数量

        Args:
            file_path: 知识文件路径
            knowledge_type: 知识类型（concept / indicator / master / industry / general）
        """
        path = Path(file_path)
        if not path.exists():
            return 0

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return 0

        new_chunks = _chunk_markdown(text, path.name)
        if not new_chunks:
            return 0

        for chunk in new_chunks:
            chunk["type"] = knowledge_type

        # 截断超长 chunk
        for chunk in new_chunks:
            if len(chunk["text"]) > MAX_CHUNK_CHARS:
                chunk["text"] = chunk["text"][:MAX_CHUNK_CHARS] + "..."

        self.chunks.extend(new_chunks)
        self._rebuild_embeddings()
        self._dirty = True
        return len(new_chunks)

    def ingest_directory(self, directory: str, knowledge_type: str = "general") -> int:
        """批量导入目录下的所有 .md 文件"""
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return 0
        total = 0
        for md_file in sorted(dir_path.glob("**/*.md")):
            total += self.ingest(str(md_file), knowledge_type)
        return total

    # ── 语义搜索 ──────────────────────────────

    def search(
        self,
        query: str,
        k: int = 5,
        knowledge_type: str | None = None,
        min_score: float = 0.0,
    ) -> list[dict]:
        """语义搜索 top-k 结果

        Args:
            query: 查询文本
            k: 返回结果数
            knowledge_type: 按类型过滤（None = 不过滤）
            min_score: 最低相似度阈值

        Returns:
            按相似度降序的列表，每项含 text / source / section / type / score
        """
        if not self.chunks or self.embeddings is None:
            return []

        query_vec = _text_to_vector(query, self.vocab)

        # 计算余弦相似度
        scores = self.embeddings @ query_vec  # dot product of normalized vectors

        # 按类型过滤
        if knowledge_type:
            type_mask = np.array(
                [c["type"] == knowledge_type for c in self.chunks],
                dtype=bool,
            )
            scores = np.where(type_mask, scores, -1.0)

        # 获取 top-k 索引
        top_indices = np.argsort(scores)[::-1]
        results = []
        for idx in top_indices:
            if len(results) >= k:
                break
            score = float(scores[idx])
            if score < min_score:
                continue
            results.append({
                "text": self.chunks[idx]["text"],
                "source": self.chunks[idx]["source"],
                "section": self.chunks[idx]["section"],
                "type": self.chunks[idx]["type"],
                "score": round(score, 4),
            })
        return results

    # ── 持久化 ────────────────────────────────

    def save(self):
        """持久化到磁盘：chunks 存 JSON，embeddings 存 .npy"""
        # chunks
        chunks_path = self.base_path / "chunks.json"
        serializable_chunks = []
        for c in self.chunks:
            serializable_chunks.append({
                "text": c["text"],
                "source": c["source"],
                "section": c["section"],
                "type": c["type"],
            })
        chunks_path.write_text(
            json.dumps(serializable_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # vocab
        vocab_path = self.base_path / "vocab.json"
        vocab_path.write_text(json.dumps(self.vocab, ensure_ascii=False), encoding="utf-8")

        # embeddings
        if self.embeddings is not None:
            emb_path = self.base_path / "embeddings.npy"
            np.save(str(emb_path), self.embeddings)

        self._dirty = False

    def load(self):
        """从磁盘加载"""
        chunks_path = self.base_path / "chunks.json"
        if not chunks_path.exists():
            return

        self.chunks = json.loads(chunks_path.read_text(encoding="utf-8"))

        vocab_path = self.base_path / "vocab.json"
        if vocab_path.exists():
            self.vocab = json.loads(vocab_path.read_text(encoding="utf-8"))

        emb_path = self.base_path / "embeddings.npy"
        if emb_path.exists():
            self.embeddings = np.load(str(emb_path))
        else:
            self._rebuild_embeddings()

    def clear(self):
        """清空所有数据"""
        self.chunks.clear()
        self.embeddings = None
        self.vocab.clear()
        self._dirty = True

    # ── 内部方法 ──────────────────────────────

    def _rebuild_embeddings(self):
        """重建所有 chunk 的向量矩阵"""
        if not self.chunks:
            self.embeddings = None
            self.vocab = {}
            return

        self.vocab = _build_vocab(self.chunks)
        vectors = [_text_to_vector(c["text"], self.vocab) for c in self.chunks]
        self.embeddings = np.stack(vectors)
