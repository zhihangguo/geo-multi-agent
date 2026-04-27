"""
自动驾驶评估 LangGraph 图

图结构：
用户问题 → 安全检查 → 意图分析 → [数据查询/日志分析/报告生成/语义搜索] → 输出过滤 → 返回

节点：
- security_node: 输入安全校验
- intent_node: 意图分析
- query_node: Text2SQL/向量查询
- analyze_node: 日志分析
- report_node: 报告生成
- semantic_node: 语义搜索
- filter_node: 输出过滤
"""
import asyncio
import json
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from contextlib import AsyncExitStack
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from openai import AsyncOpenAI

# Support standalone execution
import sys
import os
if __name__ == "__main__":
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from state import AutopilotGraphState
    from prompts import AUTOPILOT_AGENT_PROMPT
    from tools import AUTOPILOT_TOOLS
else:
    from .state import AutopilotGraphState
    from .prompts import AUTOPILOT_AGENT_PROMPT
    from .tools import AUTOPILOT_TOOLS
from config.settings import settings
from infrastructure.logging.logger import logger
from utils.response_util import ResponseFactory
from utils.text_util import format_tool_call_html
from schemas.response import ContentKind

# 流式输出队列
_stream_queue_var: ContextVar[asyncio.Queue | None] = ContextVar("autopilot_stream_queue", default=None)


async def _emit_sse(text: str, kind: ContentKind):
    """节点内部调用：将 SSE 推入队列"""
    queue = _stream_queue_var.get()
    if queue is not None:
        sse = "data: " + ResponseFactory.build_text(text, kind).model_dump_json() + "\n\n"
        await queue.put(sse)


async def _call_llm(system_prompt: str, user_content: str) -> str:
    """调用 LLM 生成文本"""
    client = AsyncOpenAI(
        base_url=getattr(settings, "AL_BAILIAN_BASE_URL", settings.SF_BASE_URL),
        api_key=getattr(settings, "AL_BAILIAN_API_KEY", settings.SF_API_KEY),
    )
    response = await client.chat.completions.create(
        model=settings.MAIN_MODEL_NAME or "Qwen/Qwen3-32B",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


async def security_node(state: AutopilotGraphState) -> dict:
    """安全检查节点"""
    query = state.get("user_query", "")
    logger.info(f"[Autopilot Security] 校验查询: {query[:50]}")

    # 简单安全规则检查
    forbidden_patterns = [
        "ignore previous", "forget everything", "you are now",
        "system:", "<system>", "### instruction", "act as",
    ]
    for pattern in forbidden_patterns:
        if pattern.lower() in query.lower():
            return {
                "final_output": "检测到潜在的注入攻击，请求已拒绝。",
                "process_logs": ["🛡️ [安全检查] 拒绝请求: 检测到注入模式"],
            }

    if not query or len(query) > 2000:
        return {
            "final_output": "查询不能为空或超过 2000 字符。",
            "process_logs": ["🛡️ [安全检查] 拒绝请求: 长度异常"],
        }

    return {"process_logs": ["🛡️ [安全检查] 通过"]}


async def intent_node(state: AutopilotGraphState) -> dict:
    """意图分析节点"""
    query = state.get("user_query", "")
    await _emit_sse("🧠 [自动驾驶评估] 正在分析任务...", ContentKind.THINKING)

    intent_prompt = (
        "分析用户意图，返回 JSON：{\"task_type\": \"query|analyze|report|semantic|unknown\", "
        "\"params\": {}, \"description\": \"...\"}\n"
        "task_type 说明：\n"
        "- query: 查询数据库记录（测试、感知、安全、规划等）\n"
        "- analyze: 分析系统日志\n"
        "- report: 生成评估报告\n"
        "- semantic: 语义搜索测试记录\n"
        "- unknown: 无法识别意图\n"
    )

    result = await _call_llm(intent_prompt, query)

    try:
        intent = json.loads(result)
    except json.JSONDecodeError:
        intent = {"task_type": "query", "params": {}, "description": query}

    await _emit_sse(f"🎯 [意图识别] {intent.get('description', query[:30])}", ContentKind.PROCESS)

    return {
        "current_task": intent,
        "process_logs": [f"🎯 [意图识别] {intent.get('task_type', 'unknown')}"],
    }


def route_by_intent(state: AutopilotGraphState) -> str:
    """根据意图路由到对应节点"""
    task = state.get("current_task", {})
    task_type = task.get("task_type", "query")

    routes = {
        "query": "query",
        "analyze": "analyze",
        "report": "report",
        "semantic": "semantic",
    }
    return routes.get(task_type, "query")


async def query_node(state: AutopilotGraphState) -> dict:
    """数据查询节点（Text2SQL / 向量搜索）"""
    query = state.get("user_query", "")
    tenant_id = state.get("tenant_id", "default")
    await _emit_sse("🔍 [数据查询] 正在查询数据库...", ContentKind.PROCESS)

    # 调用工具
    tool = AUTOPILOT_TOOLS[0]  # query_autopilot_data
    result = await tool(query, tenant_id)

    await _emit_sse(result[:200] + "..." if len(result) > 200 else result, ContentKind.ANSWER)

    return {
        "final_output": result,
        "completed_tasks": [f"query: {query[:30]}"],
        "tool_calls": ["query_autopilot_data"],
    }


async def analyze_node(state: AutopilotGraphState) -> dict:
    """日志分析节点"""
    query = state.get("user_query", "")
    tenant_id = state.get("tenant_id", "default")
    task = state.get("current_task", {})
    params = task.get("params", {})
    await _emit_sse("📊 [日志分析] 正在分析系统日志...", ContentKind.PROCESS)

    tool = AUTOPILOT_TOOLS[1]  # analyze_driving_logs
    run_id = params.get("run_id", "RUN-001")
    result = await tool(run_id, tenant_id)

    await _emit_sse(result[:200] + "..." if len(result) > 200 else result, ContentKind.ANSWER)

    return {
        "final_output": result,
        "completed_tasks": [f"analyze: {run_id}"],
        "tool_calls": ["analyze_driving_logs"],
    }


async def report_node(state: AutopilotGraphState) -> dict:
    """报告生成节点"""
    query = state.get("user_query", "")
    tenant_id = state.get("tenant_id", "default")
    task = state.get("current_task", {})
    params = task.get("params", {})
    await _emit_sse("📋 [评估报告] 正在生成报告...", ContentKind.PROCESS)

    tool = AUTOPILOT_TOOLS[3]  # generate_evaluation_report
    run_id = params.get("run_id", "RUN-001")
    result = await tool(run_id, tenant_id)

    await _emit_sse(result[:200] + "..." if len(result) > 200 else result, ContentKind.ANSWER)

    return {
        "final_output": result,
        "completed_tasks": [f"report: {run_id}"],
        "tool_calls": ["generate_evaluation_report"],
    }


async def semantic_node(state: AutopilotGraphState) -> dict:
    """语义搜索节点"""
    query = state.get("user_query", "")
    tenant_id = state.get("tenant_id", "default")
    task = state.get("current_task", {})
    params = task.get("params", {})
    await _emit_sse("🔎 [语义搜索] 正在搜索向量库...", ContentKind.PROCESS)

    tool = AUTOPILOT_TOOLS[5]  # semantic_search_runs
    result = await tool(query, tenant_id, params.get("scenario_type"), params.get("weather"))

    await _emit_sse(result[:200] + "..." if len(result) > 200 else result, ContentKind.ANSWER)

    return {
        "final_output": result,
        "completed_tasks": [f"semantic: {query[:30]}"],
        "tool_calls": ["semantic_search_runs"],
    }


# ===== 图构建 =====
def build_autopilot_app():
    """构建自动驾驶评估 LangGraph"""
    graph = StateGraph(AutopilotGraphState)

    graph.add_node("security", security_node)
    graph.add_node("intent", intent_node)
    graph.add_node("query", query_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("report", report_node)
    graph.add_node("semantic", semantic_node)

    graph.set_entry_point("security")
    graph.add_edge("security", "intent")
    graph.add_conditional_edges("intent", route_by_intent, {
        "query": "query",
        "analyze": "analyze",
        "report": "report",
        "semantic": "semantic",
    })

    for node_name in ("query", "analyze", "report", "semantic"):
        graph.add_edge(node_name, END)

    return graph.compile()


async def run_autopilot_stream(user_query: str, tenant_id: str = "default") -> AsyncGenerator[str, None]:
    """流式运行自动驾驶评估图"""
    try:
        app = build_autopilot_app()

        initial_state: AutopilotGraphState = {
            "messages": [],
            "user_query": user_query,
            "tenant_id": tenant_id,
            "current_task": None,
            "process_logs": [],
            "final_output": "",
            "search_mode": "auto",
        }

        stream_queue = asyncio.Queue()
        _stream_queue_var.set(stream_queue)

        async def run_graph():
            try:
                async for chunk in app.astream(initial_state, stream_mode="updates"):
                    for node_name, node_output in chunk.items():
                        process_logs = node_output.get("process_logs", [])
                        for log in process_logs:
                            await stream_queue.put(
                                "data: " + ResponseFactory.build_text(log, ContentKind.PROCESS).model_dump_json() + "\n\n"
                            )
                        final = node_output.get("final_output", "")
                        if final:
                            await stream_queue.put(
                                "data: " + ResponseFactory.build_text(final, ContentKind.ANSWER).model_dump_json() + "\n\n"
                            )
                await stream_queue.put(None)
            except Exception as e:
                logger.error(f"Autopilot graph execution failed: {e}", exc_info=True)
                await stream_queue.put(
                    "data: " + ResponseFactory.build_text(f"❌ 执行失败: {str(e)}", ContentKind.PROCESS).model_dump_json() + "\n\n"
                )
                await stream_queue.put(None)

        graph_task = asyncio.create_task(run_graph())

        try:
            while True:
                sse = await stream_queue.get()
                if sse is None:
                    break
                yield sse
        finally:
            if not graph_task.done():
                graph_task.cancel()
                try:
                    await graph_task
                except asyncio.CancelledError:
                    pass

        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

    except Exception as e:
        logger.error(f"Autopilot stream failed: {e}", exc_info=True)
        yield "data: " + ResponseFactory.build_text(f"❌ 流式运行失败: {str(e)}", ContentKind.PROCESS).model_dump_json() + "\n\n"
        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
    finally:
        _stream_queue_var.set(None)


if __name__ == "__main__":
    import webbrowser
    import tempfile

    app = build_autopilot_app()
    graph = app.get_graph()

    mermaid = graph.draw_mermaid()

    print("=" * 60)
    print("Autopilot LangGraph 结构 (Mermaid)")
    print("=" * 60)
    print(mermaid)
    print("=" * 60)
    print()
    print("正在浏览器中打开图形预览...")

    # 生成 HTML 并在浏览器中打开
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>LangGraph Structure</title></head>
    <body>
    <pre class="mermaid">
    {mermaid}
    </pre>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
    </body>
    </html>
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        webbrowser.open("file://" + f.name)
