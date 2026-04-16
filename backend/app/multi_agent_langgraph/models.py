from langchain_openai import ChatOpenAI
from config.settings import settings


def build_main_model() -> ChatOpenAI:
    """构建调度用主模型 (LangChain)."""
    return ChatOpenAI(
        base_url=settings.SF_BASE_URL,
        api_key=settings.SF_API_KEY,
        model=settings.MAIN_MODEL_NAME,
        temperature=0,
    )


def build_sub_model() -> ChatOpenAI:
    """构建执行用子模型 (LangChain)."""
    return ChatOpenAI(
        base_url=settings.AL_BAILIAN_BASE_URL,
        api_key=settings.AL_BAILIAN_API_KEY,
        model=settings.SUB_MODEL_NAME,
        temperature=0,
    )
