"""
Phase 5 集成测试：图片描述服务（Mock SiliconFlow 多模态 API）

学习目标：
- 理解多模态 API 的 image_url content 格式
- 理解 Markdown 图片语法的正则匹配
- 理解失败不中断的降级策略
"""
import pytest
from unittest.mock import patch, MagicMock
import httpx
from services.image_description_service import ImageDescriptionService


class TestImageDescription:
    """ImageDescriptionService 测试套件"""

    def test_describe_chunk_images_with_images(self, mock_image_description_response):
        """含图片的 chunk：图片语法被替换为文字描述"""
        chunk_text = "这是一段文本说明![岩石显微照片](http://example.com/rock.png)更多内容。"

        with patch("services.image_description_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_image_description_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = ImageDescriptionService()
            result = service.describe_chunk_images(chunk_text)

        assert "![岩石显微照片]" not in result, "原始 Markdown 图片语法应被替换"
        assert "[图片内容:" in result, "应替换为 [图片内容: 描述] 格式"
        assert "显微照片" in result, "描述内容应包含在替换后的文本中"

    def test_describe_chunk_images_no_images(self):
        """无图片的 chunk：原样返回"""
        chunk_text = "这是一段纯文本，没有任何图片。"

        service = ImageDescriptionService()
        result = service.describe_chunk_images(chunk_text)

        assert result == chunk_text, "无图片时应原样返回"

    def test_multiple_images_sequential(self, mock_image_description_response):
        """多张图片：每张都被替换"""
        chunk_text = "图1![图1](http://img1.png)中间文字图2![图2](http://img2.png)结尾"

        with patch("services.image_description_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_image_description_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = ImageDescriptionService()
            result = service.describe_chunk_images(chunk_text)

        assert result.count("[图片内容:") == 2, "两张图片应都被替换"
        assert "![" not in result, "不应保留原始图片语法"

    def test_api_failure_preserves_syntax(self):
        """API 调用失败：保留原始图片语法，不中断"""
        chunk_text = "文本![图](http://img.png)更多"

        with patch("services.image_description_service.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=MagicMock(status_code=500)
            )

            service = ImageDescriptionService()
            result = service.describe_chunk_images(chunk_text)

        assert "![图](http://img.png)" in result, "API 失败时应保留原始图片语法"

    def test_alt_text_in_prompt(self, mock_image_description_response):
        """alt 文本作为上下文传递给模型"""
        chunk_text = "![花岗岩薄片](http://example.com/granite.png)"

        with patch("services.image_description_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_image_description_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            service = ImageDescriptionService()
            service.describe_chunk_images(chunk_text)

            # 验证 API 请求中包含 alt 文本
            call_args = mock_client.return_value.__enter__.return_value.post.call_args
            json_data = call_args[1]["json"]
            text_content = json_data["messages"][0]["content"][1]["text"]
            assert "花岗岩薄片" in text_content, "alt 文本应出现在 Prompt 中"
