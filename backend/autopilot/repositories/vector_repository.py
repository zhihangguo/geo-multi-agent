"""
ChromaDB 向量存储 — 带租户隔离

存储策略：
- 每个租户独立的 collection (autopilot_tenant_a, autopilot_tenant_b)
- 物理隔离保证数据不会跨租户泄露
- 使用 OpenAI 兼容 embedding 模型（通过 LLM API），避免 ONNX 模型下载失败
"""
import os
import uuid
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from config.settings import autopilot_settings


class AutopilotVectorRepository:
    """
    自动驾驶评估向量数据库访问

    每个租户独立的 collection:
        autopilot_tenant_a
        autopilot_tenant_b
    """

    # 全局共享的 embedding 函数（延迟初始化）
    _embedding_function = None

    @classmethod
    def _get_embedding_function(cls):
        if cls._embedding_function is None:
            api_key = autopilot_settings.LLM_API_KEY
            base_url = autopilot_settings.LLM_BASE_URL

            if api_key and base_url:
                cls._embedding_function = OpenAIEmbeddingFunction(
                    api_key=api_key,
                    api_base=base_url,
                    model_name="text-embedding-v3",
                )
        return cls._embedding_function

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.collection_name = f"autopilot_{tenant_id}"

        # 确保路径存在
        os.makedirs(autopilot_settings.VECTOR_STORE_PATH, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=autopilot_settings.VECTOR_STORE_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # 创建或获取 collection，指定 embedding 函数
        embed_fn = self._get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embed_fn,
        )

    def add_document(
        self,
        document_text: str,
        metadata: dict[str, Any],
        doc_id: str | None = None,
    ) -> str:
        """添加文档到向量库"""
        if doc_id is None:
            doc_id = f"{self.tenant_id}_{uuid.uuid4().hex[:12]}"

        # 强制注入 tenant_id
        metadata["tenant_id"] = self.tenant_id

        self.collection.add(
            documents=[document_text],
            metadatas=[metadata],
            ids=[doc_id],
        )
        return doc_id

    def add_batch(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        doc_ids: list[str] | None = None,
    ) -> list[str]:
        """批量添加"""
        if doc_ids is None:
            doc_ids = [f"{self.tenant_id}_{uuid.uuid4().hex[:12]}" for _ in documents]

        # 强制注入 tenant_id
        for m in metadatas:
            m["tenant_id"] = self.tenant_id

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=doc_ids,
        )
        return doc_ids

    def semantic_search(
        self,
        query: str,
        where_filter: dict[str, Any] | None = None,
        n_results: int = 10,
    ) -> dict[str, Any]:
        """
        语义搜索 + 可选的结构化过滤

        示例 where_filter:
            {"scenario_type": "highway", "weather": "rainy"}
        """
        conditions = [{"tenant_id": {"$eq": self.tenant_id}}]
        if where_filter:
            conditions.append({k: {"$eq": v} for k, v in where_filter.items()})

        results = self.collection.query(
            query_texts=[query],
            where={"$and": conditions} if len(conditions) > 1 else conditions[0],
            n_results=n_results,
        )
        return results

    def delete_document(self, doc_id: str) -> bool:
        """删除指定文档"""
        try:
            self.collection.delete(ids=[doc_id], where={"tenant_id": self.tenant_id})
            return True
        except Exception:
            return False

    def get_collection_count(self) -> int:
        """获取文档总数"""
        return self.collection.count()

    def delete_collection(self):
        """删除整个 collection（危险操作）"""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
