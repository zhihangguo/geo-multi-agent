import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config.settings import settings


class RerankerService:
    """
    Cross-Encoder Re-ranker：基于 SiliconFlow API
    使用 BAAI/bge-reranker-v2-m3 模型对候选文档进行精细相关性排序
    """

    def __init__(self):
        self.base_url = settings.BASE_URL
        self.api_key = settings.API_KEY
        self.model = settings.RERANKER_MODEL

    def rerank(self, query: str, documents, top_n: int = 10) -> list:
        """
        对候选文档列表进行 Cross-Encoder 重排

        Args:
            query: 用户查询问题
            documents: 候选文档列表（来自 RRF 融合 + 去重后的结果）
            top_n: 返回 Top-N 篇最相关的文档

        Returns:
            list[tuple[Document, float]]: 按重排分数降序排列的 (文档, relevance_score) 列表
        """
        if not documents:
            return []

        top_n = min(top_n, len(documents))

        try:
            with httpx.Client(trust_env=False, timeout=30.0) as client:
                resp = client.post(
                    f"{self.base_url}/rerank",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "query": query,
                        "documents": [doc.page_content for doc in documents],
                        "top_n": top_n,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("results", []):
                idx = item["index"]
                score = item["relevance_score"]
                results.append((documents[idx], score))

            results.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"[Re-ranker] 对 {len(documents)} 篇候选文档重排，返回 Top-{len(results)}")
            return results

        except httpx.TimeoutException:
            logger.warning("[Re-ranker] 调用超时，降级为原始排序")
            return [(doc, 0.0) for doc in documents]
        except Exception as e:
            logger.error(f"[Re-ranker] 调用失败: {e}，降级为原始排序")
            return [(doc, 0.0) for doc in documents]
