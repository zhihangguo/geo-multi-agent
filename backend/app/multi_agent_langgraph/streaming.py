"""
LangGraph SSE 流式输出模块

提供 SSE 事件的构建工具函数。
注意：主要的流式逻辑已移至 graph.py 的 run_langgraph_stream 中，
本模块保留 emit 工具函数供兼容使用。
"""
from collections.abc import AsyncGenerator
from typing import Optional

from schemas.response import ContentKind
from utils.response_util import ResponseFactory


async def emit_process_logs(process_logs: list[str]) -> AsyncGenerator[str, None]:
    """将过程日志逐条转为 SSE PROCESS 事件。"""
    for log in process_logs:
        yield "data: " + ResponseFactory.build_text(
            log, ContentKind.PROCESS
        ).model_dump_json() + "\n\n"


def emit_final_answer(final_output: Optional[str]) -> str:
    """构建最终答案的 SSE ANSWER 事件。"""
    text = final_output or ""
    return "data: " + ResponseFactory.build_text(
        text, ContentKind.ANSWER
    ).model_dump_json() + "\n\n"


def emit_finish() -> str:
    """构建流结束信号。"""
    return "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
