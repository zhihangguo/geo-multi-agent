"""
LangGraph 状态定义模块

使用 Annotated + reducer 实现状态自动合并，
避免手动 {**state, ...} 导致的数据覆盖问题。
"""
import operator
from typing import TypedDict, List, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict, total=False):
    """LangGraph 多智能体协作状态"""

    # ---- 消息与查询 ----
    messages: Annotated[list[BaseMessage], add_messages]  # 对话历史（自动追加合并）
    user_query: str                                        # 用户原始查询

    # ---- 多任务编排 ----
    pending_tasks: list[dict]          # 待执行任务队列 [{"type": "technical"|"service", "query": "..."}]
    current_task: Optional[dict]       # 当前正在执行的任务
    completed_tasks: Annotated[list[str], operator.add]  # 已完成任务描述（自动追加）

    # ---- 最终输出 ----
    final_output: str                  # 最终拼接输出

    # ---- 可观测性 ----
    process_logs: Annotated[list[str], operator.add]   # 流程日志（自动追加）
    tool_calls: Annotated[list[str], operator.add]     # 实际工具调用记录（自动追加）
    agent_trace: Annotated[list[str], operator.add]    # Agent 路由轨迹（自动追加）
