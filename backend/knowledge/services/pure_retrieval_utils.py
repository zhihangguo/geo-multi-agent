"""
纯函数工具模块：不包含任何外部依赖（jieba、httpx 等）
这些函数被 retrieval_service.py 和测试文件共同使用。

包含：
- deduplicate_results: 基于内容前缀的去重
- rrf_fusion: Reciprocal Rank Fusion 融合算法
- dynamic_cutoff: 基于分数的动态阈值截断
"""
from typing import List
from langchain_core.documents import Document


def deduplicate_results(documents: List[Document], prefix_chars: int = 200) -> List[Document]:
    """
    基于内容前缀去重检索结果（通用函数，所有检索路径共享）
    同一个 chunk 可能出现在多个召回路径中，按前 prefix_chars 字符去重
    """
    seen = set()
    unique = []
    for doc in documents:
        key = doc.page_content[:prefix_chars].strip()
        if key not in seen:
            seen.add(key)
            unique.append(doc)
    return unique


def rrf_fusion(vector_results: List[tuple], keyword_results: List[tuple], k: int = 60) -> List[tuple[Document, float]]:
    """
    Reciprocal Rank Fusion（RRF）融合两路召回结果。
    公式：score = Σ 1 / (k + rank_i)，其中 rank_i 为文档在第 i 路中的排名（从 0 开始）

    Args:
        vector_results: 向量检索结果列表，每个元素为 (Document, score)
        keyword_results: 关键词检索结果列表，每个元素为 (Document, score)
        k: 平滑参数，默认 60（RRF 论文推荐值）

    Returns:
        按 RRF 分数降序排列的 (Document, fused_score) 列表
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for rank, (doc, _) in enumerate(vector_results):
        doc_id = doc.page_content[:200]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = doc

    for rank, (doc, _) in enumerate(keyword_results):
        doc_id = doc.page_content[:200]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(doc_map[doc_id], score) for doc_id, score in ranked]


def dynamic_cutoff(documents_with_scores: List[tuple],
                   threshold: float = 0.5,
                   min_return: int = 1,
                   max_return: int = 10) -> List[Document]:
    """
    基于 Re-ranker 分数的动态阈值截断。

    核心逻辑：
    - 至少返回 min_return 篇（保底，确保 LLM 有参考资料）
    - 分数 >= threshold 且未超过 max_return 时继续返回
    - 分数低于阈值时停止返回（后续文档被认为不相关）

    Args:
        documents_with_scores: (Document, rerank_score) 列表，已按分数降序排列
        threshold: 相关性阈值，低于此分数的文档被认为不相关
        min_return: 最少返回文档数（保底）
        max_return: 最多返回文档数

    Returns:
        截断后的 Document 列表
    """
    results = []
    for doc, score in documents_with_scores:
        if len(results) < min_return:
            results.append(doc)
        elif score >= threshold and len(results) < max_return:
            results.append(doc)
        elif score < threshold:
            break
    return results
