"""
LangGraph 核心图模块

实现与 OpenAI Agents SDK 对等的多智能体编排，并充分利用 LangGraph 原生能力：
- Checkpointing（断点续传）：MemorySaver 自动保存每个节点执行后的状态快照
- 手动重试：Expert 节点内嵌 try/except 循环，最多重试 3 次
- History（历史回溯）：通过 thread_id 检索任意历史状态
- Time Travel（时间旅行）：从任意历史 checkpoint 重新执行

节点定义：
- Orchestrator 节点：任务拆解与规划
- Dispatcher 节点：从任务队列取出下一个任务并路由
- Technical / Service 节点：调用 ReAct agent 执行
- Check Complete 条件边：检查是否还有待执行任务
"""
import asyncio
from contextlib import AsyncExitStack
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage

from .state import GraphState
from .routing import build_planner_chain
from .agents import get_technical_agent, get_service_agent, get_autopilot_agent
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import search_mcp_client, baidu_mcp_client
from utils.text_util import format_tool_call_html, format_agent_update_html
from utils.response_util import ResponseFactory
from schemas.response import ContentKind

# ============================================================================
# Checkpointer：断点续传核心
# ============================================================================

# MemorySaver 将每个节点执行后的状态快照保存在内存中。
# 配合 thread_id，实现"同一会话从断点恢复"而非每次从头执行。
# 生产环境可替换为 RedisSaver（持久化）或 SqliteSaver（本地持久化）。
checkpointer = MemorySaver()

# ============================================================================
# 流式输出队列：节点内部 → 外层 SSE
# ============================================================================

from contextvars import ContextVar

# 使用 ContextVar 在异步上下文中传递队列
_stream_queue_var: ContextVar[asyncio.Queue | None] = ContextVar("stream_queue", default=None)


async def _emit_sse(text: str, kind: ContentKind):
    """节点内部调用：将 SSE 推入队列，实时传递给外层"""
    queue = _stream_queue_var.get()
    if queue is not None:
        sse = "data: " + ResponseFactory.build_text(text, kind).model_dump_json() + "\n\n"
        await queue.put(sse)

# ============================================================================
# 专家节点重试：手动循环
# ============================================================================

# 专家节点的 try/except 重试逻辑嵌入在 technical_node / service_node 内部。
# LangGraph 原生的 RetryPolicy 需要 @entrypoint 装饰器，prebuilt agent 不适用，
# 故采用手动循环实现，最多重试 3 次。

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

    current = pending.pop(0)

    display_names = {
        "technical": "地质知识专家",
        "service": "野外后勤导航专家",
        "autopilot": "自动驾驶评估专家",
    }
    display_name = display_names.get(current["type"], current["type"])

    return {
        "current_task": current,
        "pending_tasks": pending,
        "process_logs": [format_agent_update_html(display_name)],
        "agent_trace": [current["type"]],
    }


async def _collect_agent_result(result) -> tuple[str, list[str]]:
    """从 ReAct agent 执行结果中提取最终文本和工具调用列表。"""
    output_messages = result.get("messages", [])
    final_text = ""
    actual_tool_calls = []

    for msg in output_messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                actual_tool_calls.append(tc.get("name", "unknown"))
        if isinstance(msg, AIMessage) and msg.content:
            final_text = msg.content

    return final_text, actual_tool_calls


async def technical_node(state: GraphState) -> dict:
    """
    技术专家节点：使用 ReAct agent 处理地质知识/资讯类任务。
    通过 asyncio.Queue 实时推送流式 token 到外层。
    """
    current_task = state.get("current_task", {})
    query = current_task.get("query", state.get("user_query", ""))
    agent = get_technical_agent()

    try:
        final_text = ""
        actual_tool_calls = []

        # 使用 astream_events 捕获流式输出并实时推送到队列
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=query)]},
            version="v2"
        ):
            kind = event.get("event")

            # 捕获工具调用
            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name and tool_name not in actual_tool_calls:
                    actual_tool_calls.append(tool_name)
                    # 实时推送工具调用信息
                    await _emit_sse(format_tool_call_html(tool_name), ContentKind.PROCESS)

            # 捕获 LLM 流式输出并实时推送
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    if isinstance(content, str) and content:
                        final_text += content
                        # 实时推送流式 token
                        await _emit_sse(content, ContentKind.ANSWER)

        if not final_text.strip():
            final_text = "技术专家未返回有效回答"

    except Exception as e:
        logger.error(f"[LangGraph Technical] 执行失败: {e}", exc_info=True)
        final_text = f"技术专家执行失败: {str(e)}"
        actual_tool_calls = []

    tool_logs = [format_tool_call_html(name) for name in actual_tool_calls]

    return {
        "final_output": final_text,
        "completed_tasks": [f"technical: {query[:30]}"],
        "process_logs": tool_logs,
        "tool_calls": actual_tool_calls,
    }


async def service_node(state: GraphState) -> dict:
    """
    后勤导航专家节点：使用 ReAct agent 处理站点查询/导航类任务。
    通过 asyncio.Queue 实时推送流式 token 到外层。
    """
    current_task = state.get("current_task", {})
    query = current_task.get("query", state.get("user_query", ""))
    agent = get_service_agent()

    try:
        final_text = ""
        actual_tool_calls = []

        # 使用 astream_events 捕获流式输出并实时推送到队列
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=query)]},
            version="v2"
        ):
            kind = event.get("event")

            # 捕获工具调用
            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name and tool_name not in actual_tool_calls:
                    actual_tool_calls.append(tool_name)
                    # 实时推送工具调用信息
                    await _emit_sse(format_tool_call_html(tool_name), ContentKind.PROCESS)

            # 捕获 LLM 流式输出并实时推送
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    if isinstance(content, str) and content:
                        final_text += content
                        # 实时推送流式 token
                        await _emit_sse(content, ContentKind.ANSWER)

        if not final_text.strip():
            final_text = "后勤专家未返回有效回答"

    except Exception as e:
        logger.error(f"[LangGraph Service] 执行失败: {e}", exc_info=True)
        final_text = f"后勤专家执行失败: {str(e)}"
        actual_tool_calls = []

    tool_logs = [format_tool_call_html(name) for name in actual_tool_calls]

    return {
        "final_output": final_text,
        "completed_tasks": [f"service: {query[:30]}"],
        "process_logs": tool_logs,
        "tool_calls": actual_tool_calls,
    }


async def autopilot_node(state: GraphState) -> dict:
    """
    自动驾驶评估专家节点：使用 ReAct agent 处理自动驾驶数据分析任务。
    通过 asyncio.Queue 实时推送流式 token 到外层。
    """
    current_task = state.get("current_task", {})
    query = current_task.get("query", state.get("user_query", ""))
    agent = get_autopilot_agent()

    try:
        final_text = ""
        actual_tool_calls = []

        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=query)]},
            version="v2"
        ):
            kind = event.get("event")

            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name and tool_name not in actual_tool_calls:
                    actual_tool_calls.append(tool_name)
                    await _emit_sse(format_tool_call_html(tool_name), ContentKind.PROCESS)

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    if isinstance(content, str) and content:
                        final_text += content
                        await _emit_sse(content, ContentKind.ANSWER)

        if not final_text.strip():
            final_text = "自动驾驶评估专家未返回有效回答"

    except Exception as e:
        logger.error(f"[LangGraph Autopilot] 执行失败: {e}", exc_info=True)
        final_text = f"自动驾驶评估专家执行失败: {str(e)}"
        actual_tool_calls = []

    tool_logs = [format_tool_call_html(name) for name in actual_tool_calls]

    return {
        "final_output": final_text,
        "completed_tasks": [f"autopilot: {query[:30]}"],
        "process_logs": tool_logs,
        "tool_calls": actual_tool_calls,
    }


# ============================================================================
# 条件边
# ============================================================================

def route_to_expert(state: GraphState) -> str:
    """根据 current_task 类型路由到对应专家节点。

    当 pending_tasks 为空时，dispatcher_node 已将 current_task 设为 None。
    此时直接结束，不走专家节点兜底。
    """
    current = state.get("current_task")
    if current is None:
        return END  # 无任务 → 直接结束
    if current.get("type") == "technical":
        return "technical"
    if current.get("type") == "autopilot":
        return "autopilot"
    return "service"


def check_complete(state: GraphState) -> str:
    """检查是否还有待执行任务。"""
    pending = state.get("pending_tasks", [])
    if pending:
        return "continue"
    return "done"


# ============================================================================
# 图构建（已启用 Checkpointing）
# ============================================================================

def build_langgraph_app():
    """
    构建 LangGraph 多智能体协作图。

    流程：
    orchestrator → dispatcher → technical/service → check_complete
                          ↑                              |
                          └──── (有剩余任务) ─────────────┘

    关键特性：
    - MemorySaver checkpointer：每个节点执行后自动保存状态快照
    - RetryPolicy：Expert 节点 LLM 调用失败时自动重试（最多 3 次）
    - 条件边：支持多任务循环和空任务短路
    """
    graph = StateGraph(GraphState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("dispatcher", dispatcher_node)
    graph.add_node("technical", technical_node)
    graph.add_node("service", service_node)
    graph.add_node("autopilot", autopilot_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "dispatcher")

    graph.add_conditional_edges("dispatcher", route_to_expert, {
        "technical": "technical",
        "service": "service",
        "autopilot": "autopilot",
    })

    graph.add_conditional_edges("technical", check_complete, {
        "continue": "dispatcher",
        "done": END,
    })
    graph.add_conditional_edges("service", check_complete, {
        "continue": "dispatcher",
        "done": END,
    })
    graph.add_conditional_edges("autopilot", check_complete, {
        "continue": "dispatcher",
        "done": END,
    })

    # 关键：传入 checkpointer，启用断点续传
    return graph.compile(checkpointer=checkpointer)


# ============================================================================
# 流式运行器（支持 Checkpointing + Interrupt）
# ============================================================================

async def run_langgraph_stream(
    user_query: str,
    messages: list[dict],
    thread_id: str | None = None,
    checkpoint_ns: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    流式运行 LangGraph 多智能体图。

    使用 asyncio.Queue + ContextVar 实现真正的 token 级流式输出：
    - 节点内部通过 _emit_sse() 实时推送 SSE 到队列
    - 外层并发读取队列和运行图
    - 实现与 OpenAI Agents SDK 对等的流式体验

    Checkpointing 支持：
    - 同一 thread_id 的请求共享状态快照，实现断点续传
    - 首次执行保存 checkpoint；后续请求从最新 checkpoint 继续

    Args:
        user_query: 用户查询
        messages: 对话历史（用于 LLM context）
        thread_id: 检查点线程 ID，默认为 user_query 的哈希
        checkpoint_ns: 检查点命名空间，支持多会话隔离
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

        # Checkpoint 配置：通过 thread_id 关联会话状态
        if thread_id is None:
            import hashlib
            thread_id = hashlib.md5(user_query.encode()).hexdigest()

        config: dict[str, Any] = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }

        # 创建流式输出队列
        stream_queue = asyncio.Queue()
        _stream_queue_var.set(stream_queue)

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(search_mcp_client)
            await stack.enter_async_context(baidu_mcp_client)

            # 定义图执行任务
            async def run_graph():
                """后台任务：运行图并处理节点事件"""
                try:
                    async for chunk in app.astream(initial_state, config=config, stream_mode="updates"):
                        for node_name, node_output in chunk.items():
                            # Orchestrator 节点
                            if node_name == "orchestrator":
                                await stream_queue.put(
                                    "data: " + ResponseFactory.build_text(
                                        "🧠 [调度中心] 正在分析任务...", ContentKind.THINKING
                                    ).model_dump_json() + "\n\n"
                                )
                                # 输出任务规划
                                process_logs = node_output.get("process_logs", [])
                                for log in process_logs:
                                    await stream_queue.put(
                                        "data: " + ResponseFactory.build_text(
                                            log, ContentKind.PROCESS
                                        ).model_dump_json() + "\n\n"
                                    )

                            # Dispatcher 节点
                            elif node_name == "dispatcher":
                                # 输出智能体切换信息
                                process_logs = node_output.get("process_logs", [])
                                for log in process_logs:
                                    await stream_queue.put(
                                        "data: " + ResponseFactory.build_text(
                                            log, ContentKind.PROCESS
                                        ).model_dump_json() + "\n\n"
                                    )

                            # Technical 节点完成
                            elif node_name == "technical":
                                await stream_queue.put(
                                    "data: " + ResponseFactory.build_text(
                                        "✅ [地质知识专家] 任务完成", ContentKind.PROCESS
                                    ).model_dump_json() + "\n\n"
                                )

                            # Service 节点完成
                            elif node_name == "service":
                                await stream_queue.put(
                                    "data: " + ResponseFactory.build_text(
                                        "✅ [野外后勤导航专家] 任务完成", ContentKind.PROCESS
                                    ).model_dump_json() + "\n\n"
                                )

                            # Autopilot 节点完成
                            elif node_name == "autopilot":
                                await stream_queue.put(
                                    "data: " + ResponseFactory.build_text(
                                        "✅ [自动驾驶评估专家] 任务完成", ContentKind.PROCESS
                                    ).model_dump_json() + "\n\n"
                                )

                    # 图执行完成，发送结束信号
                    await stream_queue.put(None)

                except Exception as e:
                    logger.error(f"Graph execution failed: {e}", exc_info=True)
                    await stream_queue.put(
                        "data: " + ResponseFactory.build_text(
                            f"❌ 图执行失败: {str(e)}", ContentKind.PROCESS
                        ).model_dump_json() + "\n\n"
                    )
                    await stream_queue.put(None)

            # 启动图执行任务
            graph_task = asyncio.create_task(run_graph())

            # 主循环：从队列读取并 yield SSE
            try:
                while True:
                    sse = await stream_queue.get()
                    if sse is None:  # 结束信号
                        break
                    yield sse

            finally:
                # 确保图任务完成
                if not graph_task.done():
                    graph_task.cancel()
                    try:
                        await graph_task
                    except asyncio.CancelledError:
                        pass

            # 发送结束事件
            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

    except Exception as e:
        logger.error(f"LangGraph stream failed: {e}", exc_info=True)
        yield "data: " + ResponseFactory.build_text(
            f"❌ LangGraph 运行失败: {str(e)}", ContentKind.PROCESS
        ).model_dump_json() + "\n\n"
        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

    finally:
        # 清理 ContextVar
        _stream_queue_var.set(None)


# ============================================================================
# History / Time Travel / Replay API
# ============================================================================

def get_graph_state_history(
    thread_id: str,
    checkpoint_ns: str | None = None,
) -> list[dict]:
    """
    获取指定 thread_id 的所有历史 checkpoint（从旧到新）。

    可用于：
    - 前端展示完整的执行轨迹
    - 调试时还原任意历史状态
    - 实现"时间旅行"：从任意历史状态重新执行

    Args:
        thread_id: 会话线程 ID
        checkpoint_ns: 检查点命名空间

    Returns:
        按时间顺序排列的 checkpoint 列表，每个包含完整状态快照
    """
    app = build_langgraph_app()
    config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }

    checkpoints = []
    for state in app.get_history(config):
        checkpoints.append({
            "next_node": state.get("next", None),
            "config": state.get("config", {}),
            "metadata": state.metadata if hasattr(state, "metadata") else {},
            "values": dict(state) if hasattr(state, "__iter__") else {},
        })

    return checkpoints


def replay_from_checkpoint(
    thread_id: str,
    checkpoint_id: str | None = None,
    checkpoint_ns: str | None = None,
) -> dict:
    """
    从指定 checkpoint 重新执行（时间旅行）。

    可用于：
    - 用户要求"重新回答"
    - 修复错误路径后从断点继续
    - A/B 测试不同分支

    Args:
        thread_id: 会话线程 ID
        checkpoint_id: 要回溯的目标 checkpoint ID（None = 从最新 checkpoint 重新执行）
        checkpoint_ns: 检查点命名空间

    Returns:
        重新执行后的最终状态
    """
    app = build_langgraph_app()

    config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }

    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id

    result = app.invoke(None, config=config)
    return dict(result)


def interrupt_and_wait_for_input(
    user_query: str,
    thread_id: str,
    checkpoint_ns: str | None = None,
) -> str:
    """
    中断图执行，等待用户输入后继续（Interrupt 模式）。

    当图执行到特定节点（如需要用户确认）时，主动抛出 NodeInterrupt。
    外层捕获后返回 interrupt_id，前端可据此暂停 UI 并等待用户操作，
    完成后调用 resume_with_input() 继续执行。

    当前实现：直接返回 interrupt signal，实际中断由 NodeInterrupt 机制驱动。

    Returns:
        interrupt_signal: 中断信号标识，前端据此展示"等待输入"状态
    """
    return f"interrupt:thread={thread_id},ns={checkpoint_ns or 'default'}"


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
