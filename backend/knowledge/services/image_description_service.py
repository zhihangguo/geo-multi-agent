import re
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config.settings import settings


class ImageDescriptionService:
    """
    离线图片描述生成：用多模态模型为 chunk 中的图片生成文字描述

    在文档入库（ingestion）阶段调用，将 Markdown 中的图片语法
    ![alt](url) 替换为 [图片内容: 文字描述]，使 LLM 能理解图片信息。
    """

    def __init__(self):
        self.base_url = settings.BASE_URL
        self.api_key = settings.API_KEY
        self.model = settings.IMAGE_DESCRIPTION_MODEL

    def describe_chunk_images(self, chunk_text: str) -> str:
        """
        扫描 chunk 中的所有图片，逐个生成文字描述并替换

        Args:
            chunk_text: 包含 Markdown 图片语法的文档块内容

        Returns:
            str: 图片已被替换为文字描述的文本
        """
        # 匹配 Markdown 图片语法: ![alt](url)
        pattern = r'!\[([^\]]*)\]\((https?://[^\s\)]+)\)'
        matches = re.findall(pattern, chunk_text)

        if not matches:
            return chunk_text  # 无图片，直接返回

        for alt_text, url in matches:
            try:
                desc = self._describe_image(url, alt_text)
                replacement = f"[图片内容: {desc}]"
                chunk_text = chunk_text.replace(f"![{alt_text}]({url})", replacement)
                logger.info(f"[图片描述] 已替换图片: {url[:50]}...")
            except Exception as e:
                logger.warning(f"[图片描述] 生成失败，保留原始图片语法: {e}")
                # 保留原始图片语法，不做替换

        return chunk_text

    def _describe_image(self, url: str, alt_text: str) -> str:
        """
        调用多模态模型生成单张图片的文字描述

        Args:
            url: 图片 URL
            alt_text: 图片的 alt 文字（提供上下文）

        Returns:
            str: 图片的中文文字描述
        """
        with httpx.Client(trust_env=False, timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": url}
                            },
                            {
                                "type": "text",
                                "text": (
                                    f"请用中文简洁描述这张图片的内容。"
                                    f"图片的上下文描述是：{alt_text}。"
                                    f"如果是地质相关的，请特别注意岩石、矿物、构造等细节。"
                                    f"控制在50字以内。"
                                )
                            }
                        ]
                    }],
                    "max_tokens": 200,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
