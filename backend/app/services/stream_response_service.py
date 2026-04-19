from collections.abc import AsyncGenerator
from agents.run import RunResultStreaming
from openai.types.responses.response_stream_event import (
    ResponseTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)
from agents.items import ToolCallItem, ToolCallOutputItem

from utils.response_util import ResponseFactory
from utils.text_util import format_tool_call_html, format_agent_update_html
from schemas.response import ContentKind


async def process_stream_response(streaming_result: RunResultStreaming, emit_finish: bool = True) -> AsyncGenerator:
    """
    处理Agent流式的事假
    Args:
        streaming_result:  流式结果对象（RunResultStreaming）
    Returns:

    """

    async for event in streaming_result.stream_events():
        # ------------------------------------------------------------------
        # 1. 文本与推理生成事件 (Text & Reasoning)
        # ------------------------------------------------------------------
        if event.type == "raw_response_event":
            # 1.1 常规文本输出 → ANSWER
            if isinstance(event.data, ResponseTextDeltaEvent):
                delta_text = event.data.delta
                yield "data: " + ResponseFactory.build_text(
                    delta_text, ContentKind.ANSWER
                ).model_dump_json() + "\n\n"

            # 1.2 推理过程输出 → THINKING  #  是OpenAI的推理模型（o1的推理过程被OpenAI封装到ResponseReasoningTextDeltaEvent对象中）
            elif ResponseReasoningTextDeltaEvent and isinstance(event.data, ResponseReasoningTextDeltaEvent):
                if event.data.delta:
                    yield "data: " + ResponseFactory.build_text(
                        event.data.delta, ContentKind.THINKING
                    ).model_dump_json() + "\n\n"

            # 1.3 推理摘要 → THINKING   # 非OpenAI的推理模型（Qwq的推理过程被OpenAI封装到ResponseReasoningSummaryTextDeltaEvent对象中）
            elif isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                if event.data.delta:
                    yield "data: " + ResponseFactory.build_text(
                        event.data.delta, ContentKind.THINKING
                    ).model_dump_json() + "\n\n"

        # ------------------------------------------------------------------
        # 2. 工具调用事件 (Tool Call)
        # ------------------------------------------------------------------
        elif event.type == "run_item_stream_event":
            if hasattr(event, "name") and event.name == "tool_called":
                if isinstance(event.item, ToolCallItem) and event.item.type == "tool_call_item":
                    tool_name = event.item.raw_item.name
                    tool_args = event.item.raw_item.arguments

                    # 格式化工具名称映射（与 LangGraph 对齐）
                    tool_display_name = {
                        "query_knowledge_tool": "知识库查询",
                        "web_search_tool": "联网搜索",
                        "resolve_user_location_from_text": "位置解析",
                        "query_nearest_repair_shops_by_coords": "查询附近站点",
                        "map_geocode": "地址解析",
                        "map_ip_location": "IP定位",
                        "map_uri": "生成导航链接",
                    }.get(tool_name, tool_name)

                    text = format_tool_call_html(tool_display_name)
                    # 构建 PROCESS 类型消息
                    yield "data: " + ResponseFactory.build_text(
                        text, ContentKind.PROCESS
                    ).model_dump_json() + "\n\n"

            elif hasattr(event, "name") and event.name == "tool_output":
                if isinstance(event.item, ToolCallOutputItem):
                    output_text = str(event.item.output or "")
                    lowered = output_text.lower()
                    degrade_markers = [
                        "知识库查询失败", "知识库查询异常", "all connection attempts failed",
                        "connection", "timeout", "连接失败", "服务不可用", "error",
                    ]
                    if any(marker in lowered for marker in degrade_markers) or any(marker in output_text for marker in degrade_markers):
                        degrade_notice = (
                            "⚠️ 当前知识库服务不可用，系统已降级："
                            "将基于已有模型知识继续回答，结果可能不如知识库增强完整。"
                        )
                        yield "data: " + ResponseFactory.build_text(
                            degrade_notice, ContentKind.DEGRADE
                        ).model_dump_json() + "\n\n"

        # ------------------------------------------------------------------
        # 3. 智能体状态更新
        # ------------------------------------------------------------------
        elif event.type == "agent_updated_stream_event":
            new_agent_name = event.new_agent.name

            text = format_agent_update_html(new_agent_name)

            yield "data: " + ResponseFactory.build_text(
                text, ContentKind.PROCESS
            ).model_dump_json() + "\n\n"

        # ------------------------------------------------------------------
        # 4. 发送结束信号
        # ------------------------------------------------------------------
    if emit_finish:
        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
