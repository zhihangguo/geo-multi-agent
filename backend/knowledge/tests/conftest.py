"""
共享测试 fixtures — 所有测试文件都可使用。
"""
import sys
from unittest.mock import MagicMock

# Mock 所有不兼容 Python 3.12 或当前环境缺失的模块
# 必须在导入任何其他模块之前执行

_mock_jieba = MagicMock()
_mock_jieba.lcut = lambda s: list(s)
sys.modules['jieba'] = _mock_jieba

# Mock langchain_chroma（当前环境可能未安装）
sys.modules['langchain_chroma'] = MagicMock()

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document


# ========== 测试文档 Fixtures ==========

@pytest.fixture
def sample_documents():
    """3 篇不同内容的文档"""
    return [
        Document(page_content="这是关于 Windows 7 U盘安装的详细教程，包含准备工作和步骤。", metadata={"title": "如何使用U盘安装Windows 7操作系统"}),
        Document(page_content="岩石鉴定的基本方法包括肉眼观察、硬度测试和酸反应测试。", metadata={"title": "岩石鉴定方法有哪些"}),
        Document(page_content="电脑开机后屏幕无任何反应，可能是电源问题或主板故障。", metadata={"title": "开机之后无任何反应怎么办"}),
    ]


@pytest.fixture
def duplicate_documents():
    """包含重复内容的文档列表（用于去重测试）"""
    base = "A" * 200  # 前 200 字符相同
    return [
        Document(page_content=base + "suffix1_different", metadata={"title": "doc1"}),
        Document(page_content=base + "suffix2_different", metadata={"title": "doc2"}),  # 前 200 相同
        Document(page_content="B" * 250, metadata={"title": "doc3"}),  # 完全不同
    ]


@pytest.fixture
def scored_documents_for_cutoff():
    """预评分文档列表（用于 dynamic_cutoff 测试）"""
    return [
        (Document(page_content="高度相关的内容"), 0.95),
        (Document(page_content="比较相关的内容"), 0.72),
        (Document(page_content="稍微相关的内容"), 0.51),
        (Document(page_content="不太相关的内容"), 0.30),
        (Document(page_content="完全无关的内容"), 0.10),
    ]


@pytest.fixture
def scored_documents_for_rrf():
    """用于 RRF 测试的两路召回结果"""
    # 文档 A 在两路中都出现，B 只在向量路，C 只在关键词路
    doc_a = Document(page_content="文档 A 的内容：Windows 7 安装教程的详细步骤说明。")
    doc_b = Document(page_content="文档 B 的内容：其他不相关的技术文档内容。")
    doc_c = Document(page_content="文档 C 的内容：Windows 操作系统的另一个版本说明。")
    return {
        "vector_results": [(doc_a, 0.5), (doc_b, 0.8)],  # A 排第 1，B 排第 2
        "keyword_results": [(doc_c, 0.9), (doc_a, 0.3)],  # C 排第 1，A 排第 2
    }


# ========== Mock 外部 API 的 Fixtures ==========

@pytest.fixture
def mock_reranker_response():
    """Mock SiliconFlow Re-ranker API 响应"""
    return {
        "results": [
            {"index": 1, "relevance_score": 0.92},
            {"index": 0, "relevance_score": 0.45},
            {"index": 2, "relevance_score": 0.15},
        ]
    }


@pytest.fixture
def mock_image_description_response():
    """Mock SiliconFlow 多模态图片描述 API 响应"""
    return {
        "choices": [
            {"message": {"content": "一张花岗岩岩石的显微照片，可见石英和长石晶体结构。"}}
        ]
    }
