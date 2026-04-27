from pydantic_settings import BaseSettings,SettingsConfigDict
import os

class Settings(BaseSettings):
    API_KEY: str = os.environ.get("API_KEY")
    BASE_URL: str = os.environ.get("BASE_URL")
    MODEL: str = os.environ.get("MODEL")
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL")

    
    # knowledge/config
    KNOWLEDGE_BASE_URL:str=os.environ.get("KNOWLEDGE_BASE_URL")

    _current_dir = os.path.dirname(os.path.abspath(__file__))
    # knowledge
    _project_root = os.path.dirname(_current_dir)
    
    VECTOR_STORE_PATH: str = os.path.join(_project_root, "chroma_kb1")
    
    # Default directories
    CRAWL_OUTPUT_DIR: str = os.path.join(_project_root, "data", "crawl")
    # Using 'data/crawl' as the default location for markdown files
    MD_FOLDER_PATH: str = CRAWL_OUTPUT_DIR
    TMP_MD_FOLDER_PATH:str= os.path.join(_project_root, "data", "tmp")
    # Text splitting configuration
    CHUNK_SIZE: int = 3000
    CHUNK_OVERLAP: int = 200

    # Retrieval configuration
    TOP_ROUGH: int = 50       # 粗排返回数量（标题检索用）
    TOP_RECALL: int = 30      # 每路召回数量（Phase 2：多路召回）
    TOP_RERANK: int = 20      # 送入 Re-ranker 的候选数量（Phase 3 用）
    TOP_FINAL: int = 10       # 最终返回给 LLM 的文档数（Phase 4 动态阈值前最大限制）

    # Re-ranker model configuration（Phase 3）
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # Dynamic threshold configuration（Phase 4）
    RERANK_THRESHOLD: float = 0.5   # Re-ranker 相关性阈值
    MIN_RETURN: int = 1             # 最少返回文档数（保底）
    MAX_RETURN: int = 10            # 最多返回文档数

    # Image multimodal configuration（Phase 5）
    ENABLE_IMAGE_DESCRIPTION: bool = True
    IMAGE_DESCRIPTION_MODEL: str = "Qwen/Qwen2.5-VL-72B-Instruct"

    model_config = SettingsConfigDict(
        env_file=os.path.join(_project_root, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# 必须要实例化
settings = Settings()
