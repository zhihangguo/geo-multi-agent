"""
完整检索管线集成测试（Mock 所有外部依赖）

学习目标：
- 理解完整检索流程：双路召回 → RRF → 去重 → Re-ranker → 动态阈值
- 理解 rerank_score 如何写入 document metadata
- 理解 Re-ranker 失败时的降级行为
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from services.retrieval_service import RetrievalService


class TestRetrievalPipeline:
    """RetrievalService.retrieval() 完整流程测试"""

    def _mock_all_dependencies(self):
        """Mock 所有外部依赖的辅助方法"""
        # Mock 向量检索结果
        mock_vector_results = [
            (Document(page_content="Windows 7 U盘安装的详细步骤和注意事项", metadata={"title": "Windows 7安装"}), 0.3),
            (Document(page_content="岩石鉴定的基本方法和技巧", metadata={"title": "岩石鉴定"}), 0.5),
        ]

        # Mock 标题关键词检索结果
        mock_keyword_results = [
            (Document(page_content="关于 Windows 操作系统安装的说明", metadata={"title": "Windows 7安装"}), 0.8),
        ]

        # Mock Re-ranker 结果
        mock_reranked = [
            (Document(page_content="Windows 7 U盘安装的详细步骤和注意事项", metadata={"title": "Windows 7安装"}), 0.92),
            (Document(page_content="关于 Windows 操作系统安装的说明", metadata={"title": "Windows 7安装"}), 0.85),
            (Document(page_content="岩石鉴定的基本方法和技巧", metadata={"title": "岩石鉴定"}), 0.30),
        ]

        return mock_vector_results, mock_keyword_results, mock_reranked

    def test_full_pipeline_returns_documents_with_scores(self):
        """完整流程：返回的文档应带有 rerank_score metadata"""
        mock_vector, mock_keyword, mock_reranked = self._mock_all_dependencies()

        with patch.object(RetrievalService, "__init__", lambda self: None):
            service = RetrievalService()
            service.chroma_vector = MagicMock()
            service.reranker = MagicMock()
            service.spliter = MagicMock()

            service.chroma_vector.search_similarity_with_score.return_value = mock_vector
            service.reranker.rerank.return_value = mock_reranked

            with patch("services.retrieval_service.MarkDownUtils.collect_md_metadata", return_value=[]):
                with patch("services.retrieval_service.RetrievalService.rough_ranking", return_value=[]):
                    with patch("services.retrieval_service.RetrievalService.fine_ranking", return_value=[]):
                        result = service.retrieval("如何安装 Windows 7")

        # 验证返回了文档
        assert len(result) > 0, "应返回至少 1 篇文档"
        # 验证 rerank_score 被写入 metadata
        assert "rerank_score" in result[0].metadata, "返回文档应包含 rerank_score"

    def test_rerank_score_written_to_metadata(self):
        """验证 Re-ranker 分数正确写入 document metadata"""
        mock_vector = [(Document(page_content="内容A"), 0.1)]
        mock_reranked = [(Document(page_content="内容A"), 0.95)]

        with patch.object(RetrievalService, "__init__", lambda self: None):
            service = RetrievalService()
            service.chroma_vector = MagicMock()
            service.reranker = MagicMock()
            service.spliter = MagicMock()

            service.chroma_vector.search_similarity_with_score.return_value = mock_vector
            service.reranker.rerank.return_value = mock_reranked

            with patch("services.retrieval_service.MarkDownUtils.collect_md_metadata", return_value=[]):
                with patch("services.retrieval_service.RetrievalService.rough_ranking", return_value=[]):
                    with patch("services.retrieval_service.RetrievalService.fine_ranking", return_value=[]):
                        result = service.retrieval("测试查询")

        assert result[0].metadata.get("rerank_score") == 0.95, \
            "rerank_score 应正确写入 metadata"

    def test_reranker_failure_degradation(self):
        """Re-ranker 失败时：降级为 RRF 排序结果"""
        mock_vector = [(Document(page_content="降级测试内容"), 0.2)]

        with patch.object(RetrievalService, "__init__", lambda self: None):
            service = RetrievalService()
            service.chroma_vector = MagicMock()
            service.reranker = MagicMock()
            service.spliter = MagicMock()

            service.chroma_vector.search_similarity_with_score.return_value = mock_vector
            # Re-ranker 返回降级结果（原始顺序，分数 0.0）
            service.reranker.rerank.return_value = [(Document(page_content="降级测试内容"), 0.0)]

            with patch("services.retrieval_service.MarkDownUtils.collect_md_metadata", return_value=[]):
                with patch("services.retrieval_service.RetrievalService.rough_ranking", return_value=[]):
                    with patch("services.retrieval_service.RetrievalService.fine_ranking", return_value=[]):
                        result = service.retrieval("测试查询")

        # 即使 Re-ranker 失败，仍应返回结果
        assert len(result) >= 1, "Re-ranker 失败时仍应返回 RRF 排序的结果"
