"""
自动驾驶评估 LangGraph 状态定义
"""
import operator
from typing import TypedDict, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AutopilotGraphState(TypedDict, total=False):
    """自动驾驶评估 LangGraph 状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    tenant_id: str
    current_task: Optional[dict]
    process_logs: Annotated[list[str], operator.add]
    final_output: str
    search_mode: str  # "auto", "text2sql", "vector"
