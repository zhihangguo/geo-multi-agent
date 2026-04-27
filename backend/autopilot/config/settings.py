from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import model_validator
from typing_extensions import Self

# 复用主服务的 .env 配置（LLM API Key 等）
APP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "app"


class AutopilotSettings(BaseSettings):
    """自动驾驶评估服务配置"""

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "autopilot_eval"
    MYSQL_CHARSET: str = "utf8mb4"
    MYSQL_CONNECT_TIMEOUT: int = 10
    MYSQL_MAX_CONNECTIONS: int = 10

    # ChromaDB — 与 mem0_chroma 同级，统一放在 backend/ 目录下
    VECTOR_STORE_PATH: str = str(Path(__file__).resolve().parent.parent.parent / "mem0_chroma")

    # LLM — 复用主服务的阿里百炼配置（从 backend/app/.env 读取）
    AL_BAILIAN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    AL_BAILIAN_API_KEY: str = ""
    AL_BAILIAN_MODEL_NAME: str = "qwen3-max"

    # Text2SQL
    TEXT2SQL_MAX_RETRIES: int = 3
    TEXT2SQL_MAX_RESULTS: int = 100
    TEXT2SQL_CACHE_SIZE: int = 256

    # Security
    MAX_INPUT_LENGTH: int = 2000

    # 兼容别名
    @property
    def LLM_BASE_URL(self) -> str:
        return self.AL_BAILIAN_BASE_URL

    @property
    def LLM_API_KEY(self) -> str:
        return self.AL_BAILIAN_API_KEY

    @property
    def LLM_MODEL(self) -> str:
        return self.AL_BAILIAN_MODEL_NAME

    model_config = SettingsConfigDict(
        env_file=str(APP_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode='after')
    def force_autopilot_db(self) -> Self:
        """强制使用 autopilot_eval 数据库，忽略 .env 中的 MYSQL_DATABASE"""
        self.MYSQL_DATABASE = "autopilot_eval"
        return self


autopilot_settings = AutopilotSettings()
