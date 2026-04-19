from pydantic import Field
from typing import  Optional
from pydantic import BaseModel

class UserContext(BaseModel):
    """
    用户上下文信息，用于标识请求来源。
    """
    user_id: str                                                          # 当前用户的唯一标识
    session_id: Optional[str] = Field(description="会话ID", default=None)  # 可选的会话标识，用于多轮对话追踪


class RuntimeModelConfig(BaseModel):
    provider: Optional[str] = Field(default="custom", description="模型提供商标识")
    base_url: Optional[str] = Field(default=None, description="OpenAI兼容Base URL")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    model: Optional[str] = Field(default=None, description="模型名")


class ChatMessageRequest(BaseModel):
    """
    用户发起聊天请求的入参结构。
    """
    query: str           # 用户输入的查询文本
    context: UserContext # 用户上下文信息
    flag: bool = True    # 预留标志位（当前默认为 True）
    mode: Optional[str] = Field(default="agents", description="架构模式: agents | langgraph")
    runtime_model_config: Optional[RuntimeModelConfig] = Field(default=None, alias="model_config", description="运行时模型配置")


class UserSessionsRequest(BaseModel):
    """
    获取用户历史会话列表的请求体。
    """
    user_id: str = Field(description="用户唯一标识符")     # 用于查询该用户的所有会话记录


class DeleteSessionRequest(BaseModel):
    """删除用户历史会话请求体。"""
    user_id: str = Field(description="用户唯一标识符")
    session_id: str = Field(description="要删除的会话ID")


# ============================================================================
# LangGraph 原生能力 API 请求模型
# ============================================================================

class HistoryRequest(BaseModel):
    """
    获取执行历史请求体。

    用于 /api/langgraph/history 和 /api/langgraph/pause。
    """
    user_id: str = Field(description="用户唯一标识符")
    session_id: Optional[str] = Field(description="会话ID（默认使用 default_session）", default=None)
    pause_message: Optional[str] = Field(description="暂停时显示给用户的消息", default=None)


class ReplayRequest(BaseModel):
    """
    重放/恢复执行请求体。

    用于 /api/langgraph/replay 和 /api/langgraph/resume。
    """
    user_id: str = Field(description="用户唯一标识符")
    session_id: Optional[str] = Field(description="会话ID（默认使用 default_session）", default=None)
    checkpoint_id: Optional[str] = Field(description="目标 checkpoint ID（None = 从最新开始）", default=None)
    resume_input: Optional[str] = Field(description="恢复时传递给图的输入（如用户确认内容）", default=None)

