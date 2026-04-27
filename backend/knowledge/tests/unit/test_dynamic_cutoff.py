"""
Phase 4 单元测试：动态阈值截断函数 dynamic_cutoff()

学习目标：
- 理解阈值截断的核心逻辑
- 理解 min_return 保底机制的重要性
- 理解 max_return 上限保护的作用
- 理解早停（Early Stopping）的前提：输入必须已按分数降序排列
"""
import pytest
from langchain_core.documents import Document
from services.pure_retrieval_utils import dynamic_cutoff


def scored_docs(scores):
    """辅助函数：从分数列表构建 (Document, score) 列表"""
    return [(Document(page_content=f"文档{i}"), score) for i, score in enumerate(scores)]


class TestDynamicCutoff:
    """dynamic_cutoff() 测试套件"""

    def test_all_above_threshold(self):
        """所有文档分数都高于阈值 → 返回 max_return 篇"""
        docs = scored_docs([0.95, 0.87, 0.81, 0.75, 0.68, 0.55])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 6, "所有文档都达标时应全部返回（不超过 max_return）"

    def test_all_below_threshold(self):
        """所有文档分数都低于阈值 → 返回 min_return 篇（保底）"""
        docs = scored_docs([0.3, 0.2, 0.1])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 1, "即使全不达标，也应返回保底 1 篇"
        assert result[0].page_content == "文档0", "保底返回第一篇"

    def test_mixed_scores(self):
        """部分高于阈值，部分低于 → 截断"""
        docs = scored_docs([0.9, 0.7, 0.4, 0.2])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 2, "0.9 和 0.7 通过，0.4 触发截断"
        assert result[0].page_content == "文档0"
        assert result[1].page_content == "文档1"

    def test_max_return_cap(self):
        """超过 max_return 篇达标文档 → 被上限截断"""
        docs = scored_docs([0.9] * 15)  # 15 篇都 0.9 分
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 10, "最多返回 max_return 篇"

    def test_early_termination(self):
        """早停：遇到低于阈值的文档后，后续即使有高分也不返回"""
        # 注意：输入必须已排序！[0.9, 0.3, 0.8] 中 0.8 在 0.3 后面
        docs = scored_docs([0.9, 0.3, 0.8])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 1, "遇到 0.3 后停止，后面的 0.8 不会被返回"
        assert result[0].page_content == "文档0"

    def test_empty_input(self):
        """空输入返回空列表"""
        result = dynamic_cutoff([], threshold=0.5, min_return=1, max_return=10)
        assert result == []

    def test_single_doc_above(self):
        """单篇文档高于阈值 → 返回"""
        docs = scored_docs([0.8])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 1

    def test_single_doc_below(self):
        """单篇文档低于阈值 → 仍返回（min_return=1 保底）"""
        docs = scored_docs([0.1])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 1, "保底机制：即使分数低也返回 1 篇"

    def test_boundary_exact_score(self):
        """分数正好等于阈值 → 通过（>= 不是 >）"""
        docs = scored_docs([0.5, 0.5, 0.499])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=10)
        assert len(result) == 2, "0.5 等于阈值，应该通过"

    def test_custom_threshold(self):
        """自定义阈值：threshold=0.8 更严格"""
        docs = scored_docs([0.9, 0.7, 0.6, 0.5])
        result = dynamic_cutoff(docs, threshold=0.8, min_return=1, max_return=10)
        assert len(result) == 1, "只有 0.9 通过 0.8 的阈值"

    def test_min_return_zero(self):
        """min_return=0：无保底，全部低于阈值时返回 0 篇"""
        docs = scored_docs([0.1, 0.05])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=0, max_return=10)
        assert len(result) == 0, "无保底时应返回 0 篇"

    def test_max_return_one(self):
        """max_return=1：严格限制只返回 1 篇"""
        docs = scored_docs([0.9, 0.8, 0.7])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=1, max_return=1)
        assert len(result) == 1, "max_return=1 时只返回 1 篇"

    def test_min_return_greater_than_below_count(self):
        """min_return=3，但只有 2 篇高于阈值 → 返回 min_return 篇（含低于阈值的）"""
        docs = scored_docs([0.9, 0.8, 0.3, 0.2])
        result = dynamic_cutoff(docs, threshold=0.5, min_return=3, max_return=10)
        assert len(result) == 3, "保底 3 篇，即使只有 2 篇高于阈值"
