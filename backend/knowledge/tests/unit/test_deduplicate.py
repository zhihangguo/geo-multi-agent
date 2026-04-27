"""
Phase 1 单元测试：检索结果去重函数 deduplicate_results()

学习目标：
- 理解基于内容前缀的去重策略
- 理解 200 字符边界的含义
- 理解去重与 MD5 入库去重的区别
"""
import pytest
from langchain_core.documents import Document
from services.pure_retrieval_utils import deduplicate_results


class TestDeduplicate:
    """deduplicate_results() 测试套件"""

    def test_no_duplicates(self):
        """基线：3 篇不同内容全部保留"""
        docs = [
            Document(page_content="完全不同的内容A" + "x" * 200, metadata={"title": "A"}),
            Document(page_content="完全不同的内容B" + "y" * 200, metadata={"title": "B"}),
            Document(page_content="完全不同的内容C" + "z" * 200, metadata={"title": "C"}),
        ]
        result = deduplicate_results(docs)
        assert len(result) == 3, "无重复时应返回全部 3 篇"

    def test_exact_duplicate(self):
        """完全相同的两篇文档只保留第一篇"""
        content = "这是一篇关于 Windows 7 安装的详细教程" + "。" * 200
        docs = [
            Document(page_content=content, metadata={"title": "doc1"}),
            Document(page_content=content, metadata={"title": "doc2_dup"}),
            Document(page_content="另一篇不同的内容" + "！" * 200, metadata={"title": "doc3"}),
        ]
        result = deduplicate_results(docs)
        assert len(result) == 2, "重复文档应被去除"
        assert result[0].metadata["title"] == "doc1", "保留第一次出现的"
        assert result[1].metadata["title"] == "doc3"

    def test_prefix_duplicate(self):
        """前 200 字符相同但后面不同的文档被视为重复"""
        prefix = "A" * 200
        docs = [
            Document(page_content=prefix + "suffix_first", metadata={"title": "doc1"}),
            Document(page_content=prefix + "suffix_second", metadata={"title": "doc2"}),
            Document(page_content="B" * 250, metadata={"title": "doc3"}),
        ]
        result = deduplicate_results(docs)
        assert len(result) == 2, "前 200 字符相同的文档应被视为重复"
        assert result[0].metadata["title"] == "doc1"
        assert result[1].metadata["title"] == "doc3"

    def test_boundary_199_chars_same(self):
        """199 字符相同但第 200 位不同 → 两篇都保留"""
        doc1_content = "X" * 199 + "A" + "剩余内容111"
        doc2_content = "X" * 199 + "B" + "剩余内容222"
        docs = [
            Document(page_content=doc1_content, metadata={"title": "doc1"}),
            Document(page_content=doc2_content, metadata={"title": "doc2"}),
        ]
        result = deduplicate_results(docs)
        assert len(result) == 2, "第 200 字符不同时应被视为两篇不同文档"

    def test_empty_list(self):
        """空输入返回空列表"""
        result = deduplicate_results([])
        assert result == []

    def test_single_doc(self):
        """单篇文档直接返回"""
        doc = Document(page_content="唯一的一篇", metadata={"title": "only"})
        result = deduplicate_results([doc])
        assert len(result) == 1
        assert result[0].metadata["title"] == "only"

    def test_multiple_duplicates(self):
        """4 篇相同内容只保留 1 篇"""
        content = "重复内容" + "." * 200
        docs = [Document(page_content=content, metadata={"title": f"dup_{i}"}) for i in range(4)]
        result = deduplicate_results(docs)
        assert len(result) == 1, "多篇重复应只保留第一篇"
        assert result[0].metadata["title"] == "dup_0"

    def test_custom_prefix_chars(self):
        """自定义前缀长度为 50 字符"""
        # 前 50 字符相同，第 51 位不同
        prefix50 = "A" * 50
        docs = [
            Document(page_content=prefix50 + "不同内容AAAAA", metadata={"title": "doc1"}),
            Document(page_content=prefix50 + "不同内容BBBBB", metadata={"title": "doc2"}),
        ]
        # 默认 200 字符：都保留
        result_200 = deduplicate_results(docs, prefix_chars=200)
        assert len(result_200) == 2

        # 自定义 50 字符：去重
        result_50 = deduplicate_results(docs, prefix_chars=50)
        assert len(result_50) == 1, "前 50 字符相同时应被去重"
