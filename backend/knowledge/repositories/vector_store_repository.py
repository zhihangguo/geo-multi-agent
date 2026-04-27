# 1. 优先import

import os
# 禁用 Chroma 遥测（必须在 import Chroma 之前设置）
os.environ["ANONYMIZED_TELEMETRY"] = "false"

import logging
import hashlib

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)


# 2. from三方的
from langchain_chroma import Chroma
from config.settings import settings
from langchain_core.documents import Document
from langchain_openai.embeddings import OpenAIEmbeddings
from typing import List

# 3. from 自己的



class VectorStoreRepository:
    """
     作用：对向量数据库做场景读写

    """

    def __init__(self):
        """
        创建向量数据库实例
        创建嵌入模型的实例
        向量数据库能力: 1.存储向量数据 2.搜索能力（向量数据库检索器）
        """
        self.embedding = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.API_KEY,
            openai_api_base=settings.BASE_URL,
        )

        self.vector_database = Chroma(
            persist_directory=settings.VECTOR_STORE_PATH,
            collection_name="its-knowledge",
            embedding_function=self.embedding
        )


    def  add_documents(self,documents:list,batch_size:int=16)->int:
        """
        将切分之后的文档块保存到向量数据库中（入库前按内容 MD5 去重）

        Args:
            documents: 切分之后的文档块
            batch_size: 分批保存文档块的批次大小

        Returns:
            int:成功添加到向量数据库中文档块的数量(服务前端展示)

        """

        # 1. 按内容哈希去重：同一内容只保留第一次出现
        seen_hashes = set()
        unique_docs = []
        for doc in documents:
            content_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_docs.append(doc)

        total_unique = len(unique_docs)
        skipped = len(documents) - total_unique
        if skipped > 0:
            logger.info(f"[去重] 跳过 {skipped} 个重复文档块，剩余 {total_unique} 个待入库")

        # 2. 分批次写入 Chroma
        # 修复：原代码 for 循环内有 return，导致只写入第一批 16 个 chunk 就提前退出
        documents_chunks_added = 0
        try:
            for i in range(0, total_unique, batch_size):
                batch = unique_docs[i:batch_size + i]
                self.vector_database.add_documents(batch)
                documents_chunks_added += len(batch)
                logger.info(f"成功将文档块:{documents_chunks_added}/{total_unique}保存到向量数据库...")
            return documents_chunks_added
        except Exception as e:
            logger.error(f"文档块列表保存到向量数据库失败: {str(e)}")
            raise e



    def    embedd_document(self,text:str)->List[float]:
        """
          对query进行向量化
        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入后的浮点数列表

        """
        return self.embedding.embed_query(text)

    def embedd_documents(self, texts:List[str])->List[List[float]]:
        """
        对字符串列表进行向量化
        Args:
         texts: 输入文本字符串列表

        Returns:
            List[List[float]]: 嵌入后的多个文本的浮点数列表

        """
        return self.embedding.embed_documents(texts)


    def  search_similarity_with_score(self,user_question:str,top_k:int=5)->List[tuple[Document, float]]:
        """
         相似性检索带文档分数
         分数（chroma向量数据库）：返回是L2距离得分（分数值越小越相似），不是余弦相似度的得分（分数余额高越相似） 距离得分：1-余弦相似度得分
        Args:
            user_question:

        Returns:
            List[Document]: 返回基于向量检索的相似性文档列表

        """
        return self.vector_database.similarity_search_with_score(user_question,top_k)





















