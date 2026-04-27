"""
Phase 3 集成测试：Re-ranker 服务（Mock SiliconFlow API）

学习目标：
- 理解 SiliconFlow Re-ranker API 的请求/响应格式
- 理解失败降级策略（超时/错误 → 原始顺序）
- 理解 index 映射：API 返回的是原始文档列表中的索引
"""
import pytest
from unittest.mock import patch, MagicMock
import httpx
from langchain_core.documents import Document
from services.reranker_service import RerankerService


def make_docs(count):
    """辅助：创建文档列表"""
    return [Document(page_content=f"文档{i}的内容") for i in range(count)]


class TestReranker:
    """RerankerService.rerank() 测试套件"""

    def test_rerank_success(self, mock_reranker_response):
        """正常调用：API 返回 200，结果按 relevance_score 降序排列"""
        docs = make_docs(3)

        with patch("services.reranker_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_reranker_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = RerankerService()
            result = service.rerank("测试查询", docs, top_n=3)

        assert len(result) == 3
        # index=1 的文档分数最高（0.92）
        assert result[0][0].page_content == "文档1的内容"
        assert abs(result[0][1] - 0.92) < 1e-6
        # index=0 的文档分数第二（0.45）
        assert abs(result[1][1] - 0.45) < 1e-6

    def test_rerank_timeout_fallback(self):
        """超时降级：返回原始顺序，分数 0.0"""
        docs = make_docs(3)

        with patch("services.reranker_service.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("超时")

            service = RerankerService()
            result = service.rerank("测试查询", docs, top_n=3)

        assert len(result) == 3
        # 保持原始顺序
        assert result[0][0].page_content == "文档0的内容"
        assert result[0][1] == 0.0

    def test_rerank_http500_fallback(self):
        """HTTP 500 错误降级：返回原始顺序，分数 0.0"""
        docs = make_docs(2)

        with patch("services.reranker_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
            )
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = RerankerService()
            result = service.rerank("测试查询", docs, top_n=2)

        assert len(result) == 2
        assert all(score == 0.0 for _, score in result), "降级时分数应全为 0.0"

    def test_rerank_empty_documents(self):
        """空文档列表返回空"""
        service = RerankerService()
        result = service.rerank("测试查询", [])
        assert result == []

    def test_rerank_respects_top_n(self):
        """top_n 参数限制返回数量"""
        docs = make_docs(3)

        # Mock 返回 2 条结果（模拟 API 按 top_n=2 截断）
        mock_response_data = {
            "results": [
                {"index": 1, "relevance_score": 0.92},
                {"index": 0, "relevance_score": 0.45},
            ]
        }

        with patch("services.reranker_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = RerankerService()
            result = service.rerank("测试查询", docs, top_n=2)

        assert len(result) == 2, "top_n=2 应只返回 2 篇"

    def test_rerank_api_payload(self, mock_reranker_response):
        """验证发送给 API 的请求参数正确"""
        docs = [Document(page_content="查询内容1"), Document(page_content="查询内容2")]

        with patch("services.reranker_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_reranker_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = RerankerService()
            service.rerank("我的测试问题", docs, top_n=2)

            # 验证 post 调用的参数
            call_args = mock_client.return_value.__enter__.return_value.post.call_args
            url = call_args[0][0]
            json_data = call_args[1]["json"]

            assert "rerank" in url, "URL 应包含 rerank"
            assert json_data["model"] == "BAAI/bge-reranker-v2-m3"
            assert json_data["query"] == "我的测试问题"
            assert json_data["documents"] == ["查询内容1", "查询内容2"]
            assert json_data["top_n"] == 2
