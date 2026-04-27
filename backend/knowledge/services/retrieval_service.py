import logging
import jieba
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from typing import List, Dict, Any
from langchain_core.documents import Document
from repositories.vector_store_repository import VectorStoreRepository
from .ingestion.ingestion_processor import IngestionProcessor
from utils.markdown_utils import MarkDownUtils
from config.settings import settings
from sklearn.metrics.pairwise import cosine_similarity
from .reranker_service import RerankerService
from .pure_retrieval_utils import deduplicate_results, rrf_fusion, dynamic_cutoff


class RetrievalService:
    """
    负责检索的类（检索器）
    RAG:（小块：越小越好【小（无线小）】）文本嵌入模型  （完整信息：越大越大【不能无限大】）文本语言模型====准 原文档（大）--->1.小块（子） 2.稍微大一点的块（整个文档）【父】---留一个保留关系：穿针引线思想（父文档召回）
    """

    def __init__(self):
        self.chroma_vector = VectorStoreRepository()
        self.spliter = IngestionProcessor()
        self.reranker = RerankerService()

    def rough_ranking(self, user_query, mds_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
         对标题进行粗排
         基于jieba进行标题的分词匹配
        Args:
            user_query: 用户的问题
            mds_metadata: 所有md的元数据（标题【title】，路径【path】）

        Returns:
            List[Dict[str,Any]]:所有md的元数据 （标题【title】，路径【path】，标题粗排得分【rough_score】）
        """

        # 1. 用户输入问题是否存在
        if not user_query:
            return []
        ROUGHIN_WORD_WEIGHT = 0.7

        # 2.遍历mds_metadata(所有md的元数据)
        for md_metadata in mds_metadata:
            # 2.1 获取md标题
            md_metadata_title = md_metadata['title']

            # 2.2 判断标题是否存在
            if not md_metadata_title and not md_metadata_title.strip():
                continue
            # 2.3 进行分词&&算得分
            # 2.3.1 优先用字符切:set:交、并、差:jarcard算法=A N B/A U B
            user_query_char = set(user_query)
            md_metadata_title_char = set(md_metadata_title)
            unique_char = user_query_char | md_metadata_title_char
            char_score = len(user_query_char & md_metadata_title_char) / len(unique_char) if len(unique_char) > 0 else 0

            # 2.3.2 在用jieba词项切(影响因素大一些)
            user_query_word = set(jieba.lcut(user_query))
            md_metadata_title_word = set(jieba.lcut(md_metadata_title))
            unique_word = user_query_word | md_metadata_title_word
            word_score = len(user_query_word & md_metadata_title_word) / len(unique_word) if len(unique_word) > 0 else 0

            # 2.3.3 计算粗排分数：字符级+词性项级(侧重)
            roughing_score = word_score * ROUGHIN_WORD_WEIGHT + char_score * (1 - ROUGHIN_WORD_WEIGHT)

            md_metadata['roughing_score'] = float(roughing_score)

        # 3.根据标题的元数据（roughing_score）排序并且留下前50个
        return sorted(mds_metadata, key=lambda x: x['roughing_score'], reverse=True)[:50]

    def fine_ranking(self, user_query: str, rough_mds_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
         对标题进行精排
         基于嵌入模型相似性以及cosine_similarity()
        Args:
            user_query: 用户当前问题
            rough_mds_metadata: 粗排后的md元数据

        Returns:
            List[Dict[str, Any]]: 带精排分数的元数据
        """

        # 1. 判粗排元数据
        if not rough_mds_metadata:
            return []

        # 两个二维矩阵（X[样本数] Y[样本质量]） K(X, Y) = <X, Y> / (||X||*||Y||)

        # 2. 对问题向量化
        query_embedding = self.chroma_vector.embedd_document(user_query)

        # 3. 获取粗排后的标题
        roughing_title = [md_metadata['title'] for md_metadata in rough_mds_metadata]

        # 4. 标题的向量值
        roughing_title_embeddings = self.chroma_vector.embedd_documents(roughing_title)

        # 5. 计算问题和粗排标题的相似度（余弦相似分数）分数值越大 代表问题和标题越相似
        # flatten()--->一维数组[0.1,0.4,0.01,0.6...]
        # X:1  Y:[1,2,3,4,5]   similarity=[0.1,0.4,0.01,0.6,0.3]【-1,0】
        similarity = cosine_similarity([query_embedding], roughing_title_embeddings).flatten()

        # 6. 遍历粗排元数据
        ROUGH_HEIGHT = 0.3
        SIM_HEIGHT = 0.7
        for index, md_metadata in enumerate(rough_mds_metadata):

            # a. 获取精排分数(归一)
            sim = similarity[index]
            if sim < 0:
                sim = 0
            # b. 获取粗排
            roughing_score = md_metadata['roughing_score']

            # c. 加权求最终精排分数
            final_score = roughing_score * ROUGH_HEIGHT + sim * SIM_HEIGHT

            # d. 存放到md_metadata 元数据中
            md_metadata['sim_score'] = sim
            md_metadata['final_score'] = final_score

        # 7. 排序
        sim_mds_metadata = sorted(rough_mds_metadata, key=lambda x: x['final_score'], reverse=True)[:5]

        # 8. 返回
        return sim_mds_metadata

    def retrieval(self, user_question: str) -> List[Document]:
        """
         核心检索方法（检索器的入口）
         Phase 3 改造：双路召回 → RRF 融合 → 去重 → Re-ranker 精排 → Top-N 截断
        Args:
            user_question: 用户输入的问题

        Returns:
           List[Document]: 返回指定Top-N个相似性文档列表
        """

        # 第一路：向量语义检索（召回 Top30）
        vector_results = self._search_based_vector(user_question, top_k=settings.TOP_RECALL)

        # 第二路：标题关键词检索（召回 Top30）
        keyword_results = self._search_based_title(user_question)

        # RRF 融合两路召回
        fused_results = rrf_fusion(vector_results, keyword_results)

        # 去重（Phase 1：防止同一段内容重复返回）
        deduplicated = deduplicate_results([d for d, _ in fused_results])

        # Phase 3: Re-ranker 精排（取 Top_RERANK 篇送入重排）
        reranker_candidates = deduplicated[: settings.TOP_RERANK]
        reranked = self.reranker.rerank(user_question, reranker_candidates, top_n=settings.TOP_FINAL)

        # 将 Re-ranker 分数写入 metadata，供后续 Phase 4 动态阈值使用
        for doc, score in reranked:
            doc.metadata["rerank_score"] = score

        # Phase 4: 动态阈值截断（基于 Re-ranker 分数）
        result_docs = dynamic_cutoff(
            reranked,
            threshold=settings.RERANK_THRESHOLD,
            min_return=settings.MIN_RETURN,
            max_return=settings.MAX_RETURN,
        )

        # 如果截断后文档数过少，记录日志
        if len(result_docs) < settings.MIN_RETURN:
            logger.warning(f"[动态阈值] 截断后文档数({len(result_docs)})低于保底值({settings.MIN_RETURN})，返回全部")
            result_docs = [doc for doc, _ in reranked[:settings.MIN_RETURN]]

        return result_docs

    def _search_based_vector(self, user_question: str, top_k: int = None) -> List[tuple[Document, float]]:
        """
        第一路检索：基于语义相似度检索
        改造：返回带分数的元组列表（Phase 2：为 RRF 融合提供分数）

        Args:
            user_question: 用户输入的问题
            top_k: 召回数量，默认使用 settings.TOP_RECALL

        Returns:
            List[tuple[Document, float]]：(文档, Chroma L2 距离分数) 列表
        """
        if top_k is None:
            top_k = settings.TOP_RECALL

        documents_with_score = self.chroma_vector.search_similarity_with_score(user_question, top_k=top_k)
        return documents_with_score

    def _search_based_title(self, user_query: str) -> List[tuple[Document, float]]:
        """
         第二路检索：基于标题的关键词匹配检索
         改造：返回 (Document, final_score) 元组列表（Phase 2：为 RRF 融合提供分数）

        Args:
            user_query: 用户输入的问题

        Returns:
            List[tuple[Document, float]]: (文档, fine_ranking 最终分数) 列表
        """

        # 1. 获取指定目录下的文件的标题
        mds_metadata = MarkDownUtils.collect_md_metadata(settings.CRAWL_OUTPUT_DIR)

        # 2. 进行标题匹配
        # 2.1 关键词匹配（jieba）--->（比较对象：用户输入的问题 vs crawl目录下的文件标题）
        # 2.2 标题的语义匹配（比较对象：用户的输入问题  vs md目录下的 ）
        rough_mds_metadata = self.rough_ranking(user_query, mds_metadata)
        fine_mds_metadata = self.fine_ranking(user_query, rough_mds_metadata)

        # 3. 处理文档（根据标题读取标题对于的文档内容---Document(page_content,metadata={})）
        based_title_candidates: List[tuple[Document, float]] = []
        for fine_md_metadata in fine_mds_metadata:
            try:
                # 3.1 打开文件
                with open(fine_md_metadata['path'], "r", encoding="utf-8") as f:
                    content = f.read().strip()
                # 3.2 判断content内容长度
                # a.短md知识
                if len(content) < 3000:
                    # 不切分
                    doc = Document(page_content=content, metadata={
                        "path": fine_md_metadata['path'],
                        "title": fine_md_metadata['title'],
                    })
                    final_score = fine_md_metadata.get('final_score', 0.0)
                    based_title_candidates.append((doc, final_score))
                # b. 长md知识 切分
                else:
                    doc_chunks = self._deal_long_title_content(content, fine_md_metadata, user_query)
                    for chunk in doc_chunks:
                        chunk_score = chunk.metadata.get('similarity', 0.0)
                        based_title_candidates.append((chunk, chunk_score))
            except Exception as e:
                logger.error(f"打开文件失败:{e}")
                return []

        return based_title_candidates

    def _deduplicate(self, total_candidates: List[Document]) -> List[Document]:
        """
         对合并后的文档列表去重
         用set()集合去重（(title,内容的前【100】个字符)）-->key
        Args:
            total_candidates: 合并的文档列表

        Returns:
            List[Document]：唯一的文档列表
        """

        if not total_candidates:
            return []

        # 2. 定义set集合
        seen = set()
        unique_candidates = []

        # 3. 遍历合并后的每一个文档列表
        for document in total_candidates:
            # 去重（）
            clean_content = re.sub(r'^文档来源:.*?(?=(\n|#))', '', document.page_content, flags=re.DOTALL).strip()#【加上】
            key = (document.metadata['title'], clean_content[:100])
            if key not in seen:
                seen.add(key)
                unique_candidates.append(document)

        # 4. 返回唯一的
        return unique_candidates

    def _reranking(self, unique_candidates: List[Document], user_question: str) -> List[Document]:
        """
         重新计算打分&&排序
         第二路长文档已经进行了cosine_similarity()的计算（无需在次打分）
         对第一路的文档和第二路的短文档进行重新计算

        Args:
            unique_candidates: 唯一的候选文档列表
            user_question: 用户输入的问题

        Returns:
            List[Document]: 最终指定Top-N的文档列表

        """

        # 1. 判断去重合并之后文档列表是否有文档对象
        if not unique_candidates:
            return []

        need_embedding_docs = []
        need_embedding_candidates_indices = []
        score_doc = []

        # 2. 遍历去重并合并之后的文档列表(Document,score)
        for candidate_index, unique_candidate in enumerate(unique_candidates):
            # 如何去判断 第二路长文档 or  第一路的文档和第二路?
            # 2.1 第二路的长文档
            if "chunk_index" in unique_candidate.metadata and "similarity" in unique_candidate.metadata:
                score_doc.append((unique_candidate, unique_candidate.metadata['similarity']))
            # 2.2 第一路和第二路的短文档
            else:
                need_embedding_docs.append(unique_candidate)
                need_embedding_candidates_indices.append(candidate_index)

        # 3.处理需要重新计算分数的文档
        if need_embedding_docs:
            # 3.1 计算用户问题的向量
            query_embedding = self.chroma_vector.embedd_document(user_question)

            # 3.2 获取到需要向量的文档内容
            embedding_docs_content = ["文档来源:" + doc.metadata['title'] + doc.page_content for doc in
                                      need_embedding_docs]
            # 3.3 计算需要向量的文档内容
            doc_embeddings = self.chroma_vector.embedd_documents(embedding_docs_content)

            # 3.4 计算相似得分
            similarity = cosine_similarity([query_embedding], doc_embeddings).flatten()

            # 3.5 封装到带得分的文档列表
            for idx, candidate_index in enumerate(need_embedding_candidates_indices):
                score_doc.append((unique_candidates[candidate_index], similarity[idx]))

        # 4. 排序
        sorted_docs = sorted(score_doc, key=lambda x: x[1], reverse=True)

        # 5. 返回Top-N
        return [doc for doc, _ in sorted_docs[:2]]

    def _deal_long_title_content(self, content: str, fine_md_metadata: Dict[str, Any], user_query: str) -> List[
        Document]:
        """
         处理标题对应的长文本
         切分-->文档块--->算文档块和问题的相似度
        Args:
            content: 长文本
            fine_md_metadata: 长文本对应的元数据
            user_query: 用户的问题

        Returns:
            List[Document]: 和问题相似的文档块（chunk）
        """

        # 1. 对长文本切分(换成适合)
        chunks = self.spliter.document_spliter.split_text(content)

        # 2. 获取对应的标题
        doc_chunks_title = fine_md_metadata['title']

        # 3. 标题注入到文档块中（第二次结构和第一次的拼接一定要一样）TODO
        doc_chunks_inject_title = [f"文档来源:{doc_chunks_title}" + doc_chunk for doc_chunk in chunks]

        # 4. 对问题向量
        query_embedding = self.chroma_vector.embedd_document(user_query)

        # 5. 对切分后的文档块向量化
        doc_chunk_embeddings = self.chroma_vector.embedd_documents(doc_chunks_inject_title)

        # 6. 计算相似性:doc_chunks_similarity[0.8,0.6,0.7,0.1,0.9]
        doc_chunks_similarity = cosine_similarity([query_embedding], doc_chunk_embeddings).flatten()

        # 7. 获取3个相似性分数值高的三个索引 argsort->[3,1,2,0,4]->[2,0,4]--->[4,0,2]
        top_doc_chunks_indices = doc_chunks_similarity.argsort()[-3:][::-1]

        # 8. 构建最终文档对象列表(为每一个切分后的块)
        docs = []
        for i, chunk_idx in enumerate(top_doc_chunks_indices):
            doc = Document(
                page_content=doc_chunks_inject_title[chunk_idx],  # 带上
                metadata={
                    "path": fine_md_metadata['path'],
                    "title": fine_md_metadata['title'],
                    "chunk_index:": int(chunk_idx),
                    "similarity": float(doc_chunks_similarity[chunk_idx])
                }
            )
            docs.append(doc)

        return   docs


if __name__ == '__main__':
    retrival_service = RetrievalService()

    # rough_ranking_result = retrival_service.rough_ranking("我的电脑开机之后没有任何的反应"）
    # for roughing_result in rough_ranking_result[:10]:
    #     print(f"粗排---{roughing_result}")
    #
    # sim_ranking_result = retrival_service.fine_ranking("我的电脑开机之后没有任何的反应", rough_ranking_result[:10])
    #
    # for sim_result in sim_ranking_result:
    #     print(f"精排---{sim_result}")

    # result = retrival_service.retrieval("我的电脑开机之后没有任何的反应")
    # result = retrival_service.retrieval("如何安装联想的一件影音")
    # result = retrival_service.retrieval("联想手机K900常见问题汇总有哪些")
    # result = retrival_service.retrieval("如何使用U盘安装Windows 7操作系统.")
    # result = retrival_service.retrieval("开机屏幕黑屏或蓝屏报错,无法正常进入系统怎么办")
    # result = retrival_service.retrieval("我的电脑经常死机该如何解决")
    result = retrival_service.retrieval("手机、平板上的画面能无线传输到电视上播放吗") # 80-90%

    for r in result:
        print(r)
