"""
LangGraph 核心图模块

实现与 OpenAI Agents SDK 对等的多智能体编排：
- Orchestrator 节点：任务拆解与规划
- Dispatcher 节点：从任务队列取出下一个任务并路由
- Technical / Service 节点：调用 ReAct agent 执行
- Check Complete 条件边：检查是否还有待执行任务

支持真正的实时流式输出 (astream)。
"""
from contextlib import AsyncExitStack
from collections.abc import AsyncGenerator

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk

from .state import GraphState
from .routing import build_planner_chain
from .agents import get_technical_agent, get_service_agent
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import search_mcp_client, baidu_mcp_client
from utils.text_util import format_tool_call_html, format_agent_update_html
from utils.response_util import ResponseFactory
from schemas.response import ContentKind


# ============================================================================
# 图节点定义
# ============================================================================

async def orchestrator_node(state: GraphState) -> dict:
    """
    Orchestrator 节点：分析用户请求，拆解为有序任务列表。
    与 OpenAI Agents SDK 的 orchestrator prompt 行为对齐。
    """
    user_query = state.get("user_query", "")

    planner = build_planner_chain()
    task_plan = await planner(user_query)

    pending_tasks = [t.model_dump() for t in task_plan.tasks]

    task_desc = ", ".join([f"{t['type']}({t['query'][:20]}...)" for t in pending_tasks])
    logger.info(f"[LangGraph Orchestrator] 任务规划: {task_desc}")

    return {
        "pending_tasks": pending_tasks,
        "process_logs": [f"🧠 [调度中心] 识别到 {len(pending_tasks)} 个任务"],
    }


async def dispatcher_node(state: GraphState) -> dict:
    """
    Dispatcher 节点：从 pending_tasks 取出下一个任务，设置为 current_task。
    """
    pending = list(state.get("pending_tasks", []))

    if not pending:
        return {"current_task": None}

    # 取出第一个任务
    current = pending.pop(0)

    display_name = "地质知识专家" if current["type"] == "technical" else "野外后勤导航专家"

    return {
        "current_task": current,
        "pending_tasks": pending,  # 直接覆盖（非 Annotated 字段）
        "process_logs": [format_agent_update_html(display_name)],
        "agent_trace": [current["type"]],
    }


async def technical_node(state: GraphState) -> dict:
    """
    技术专家节点：使用 ReAct agent 处理地质知识/资讯类任务。
    """
    current_task = state.get("current_task", {})
    query = current_task.get("query", state.get("user_query", ""))

    agent = get_technical_agent()

    # 使用 ainvoke 执行 agent（流式在外层 graph.astream 层面处理）
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=query)]
    })

    output_messages = result.get("messages", [])
    final_text = ""
    actual_tool_calls = []

    for msg in output_messages:
        # 收集实际工具调用
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                actual_tool_calls.append(tc.get("name", "unknown"))
        # 获取最终输出（最后一条 AI 消息）
        if isinstance(msg, AIMessage) and msg.content:
            final_text = msg.content

    # 构建工具调用可视化卡片
    tool_logs = [format_tool_call_html(name) for name in actual_tool_calls]

    return {
        "final_output": final_text,
        "completed_tasks": [f"technical: {query[:30]}"],
        "process_logs": tool_logs + ["✅ [地质知识专家] 任务完成"],
        "tool_calls": actual_tool_calls,
    }


async def service_node(state: GraphState) -> dict:
    """
    后勤导航专家节点：使用 ReAct agent 处理站点查询/导航类任务。
    """
    current_task = state.get("current_task", {})
    query = current_task.get("query", state.get("user_query", ""))

    agent = get_service_agent()

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=query)]
    })

    output_messages = result.get("messages", [])
    final_text = ""
    actual_tool_calls = []

    for msg in output_messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                actual_tool_calls.append(tc.get("name", "unknown"))
        if isinstance(msg, AIMessage) and msg.content:
            final_text = msg.content

    tool_logs = [format_tool_call_html(name) for name in actual_tool_calls]

    return {
        "final_output": final_text,
        "completed_tasks": [f"service: {query[:30]}"],
        "process_logs": tool_logs + ["✅ [野外后勤导航专家] 任务完成"],
        "tool_calls": actual_tool_calls,
    }


# ============================================================================
# 条件边
# ============================================================================

def route_to_expert(state: GraphState) -> str:
    """根据 current_task 类型路由到对应专家节点。"""
    current = state.get("current_task")
    if current and current.get("type") == "technical":
        return "technical"
    return "service"


def check_complete(state: GraphState) -> str:
    """检查是否还有待执行任务。"""
    pending = state.get("pending_tasks", [])
    if pending:
        return "continue"
    return "done"


# ============================================================================
# 图构建
# ============================================================================

def build_langgraph_app():
    """
    构建 LangGraph 多智能体协作图。

    流程：
    orchestrator → dispatcher → technical/service → check_complete
                          ↑                              |
                          └──── (有剩余任务) ─────────────┘
    """
    graph = StateGraph(GraphState)

    # 注册节点
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("dispatcher", dispatcher_node)
    graph.add_node("technical", technical_node)
    graph.add_node("service", service_node)

    # 设置入口
    graph.set_entry_point("orchestrator")

    # orchestrator → dispatcher
    graph.add_edge("orchestrator", "dispatcher")

    # dispatcher → technical / service (条件路由)
    graph.add_conditional_edges("dispatcher", route_to_expert, {
        "technical": "technical",
        "service": "service",
    })

    # technical/service → check_complete (条件边)
    graph.add_conditional_edges("technical", check_complete, {
        "continue": "dispatcher",
        "done": END,
    })
    graph.add_conditional_edges("service", check_complete, {
        "continue": "dispatcher",
        "done": END,
    })

    return graph.compile()


# ============================================================================
# 流式运行器
# ============================================================================

async def run_langgraph_stream(
    user_query: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """
    流式运行 LangGraph 多智能体图。

    使用 graph.astream() + stream_mode="updates" 实现节点级流式输出，
    将每个节点的更新实时转换为 SSE packet。

    Yields:
        SSE 格式的字符串 ("data: {...}\\n\\n")
    """
    try:
        app = build_langgraph_app()

        initial_state: GraphState = {
            "messages": [],
            "user_query": user_query,
            "pending_tasks": [],
            "completed_tasks": [],
            "current_task": None,
            "final_output": "",
            "process_logs": [],
            "tool_calls": [],
            "agent_trace": [],
        }

        async with AsyncExitStack() as stack:
            # 连接 MCP 服务
            await stack.enter_async_context(search_mcp_client)
            await stack.enter_async_context(baidu_mcp_client)

            final_output_parts = []

            # 使用 astream + updates 模式获取每个节点的增量输出
            async for event in app.astream(initial_state, stream_mode="updates"):
                # event 格式: {node_name: {state_updates}}
                for node_name, updates in event.items():
                    # --- 输出过程日志 (PROCESS) ---
                    for log in updates.get("process_logs", []):
                        yield "data: " + ResponseFactory.build_text(
                            log, ContentKind.PROCESS
                        ).model_dump_json() + "\n\n"

                    # --- 收集最终输出 ---
                    if "final_output" in updates and updates["final_output"]:
                        final_output_parts.append(updates["final_output"])

            # --- 输出最终答案 (ANSWER) ---
            combined_output = "\n\n---\n\n".join(final_output_parts) if len(final_output_parts) > 1 else (final_output_parts[0] if final_output_parts else "")

            if combined_output:
                yield "data: " + ResponseFactory.build_text(
                    combined_output, ContentKind.ANSWER
                ).model_dump_json() + "\n\n"

            # --- 发送结束信号 ---
            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

    except Exception as e:
        logger.error(f"LangGraph stream failed: {e}")
        yield "data: " + ResponseFactory.build_text(
            f"❌ LangGraph 运行失败: {str(e)}", ContentKind.PROCESS
        ).model_dump_json() + "\n\n"
        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"


# ============================================================================
# 兼容旧接口（保留供参考，不再使用）
# ============================================================================

async def run_langgraph(user_query: str, messages: list[dict]) -> GraphState:
    """
    非流式运行（兼容旧接口，已废弃）。
    请使用 run_langgraph_stream 替代。
    """
    try:
        app = build_langgraph_app()
        state: GraphState = {
            "messages": [],
            "user_query": user_query,
            "pending_tasks": [],
            "completed_tasks": [],
            "current_task": None,
            "final_output": "",
            "process_logs": [],
            "tool_calls": [],
            "agent_trace": [],
        }

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(search_mcp_client)
            await stack.enter_async_context(baidu_mcp_client)
            result_state = await app.ainvoke(state)
            return result_state

    except Exception as e:
        logger.error(f"LangGraph run failed: {e}")
        return {
            "messages": [],
            "user_query": user_query,
            "process_logs": [f"[LangGraph] 运行失败: {str(e)}"],
            "final_output": f"LangGraph 运行失败: {str(e)}",
        }
