import re
import traceback
from collections.abc import AsyncGenerator

from agents import Agent, ModelSettings, OpenAIChatCompletionsModel
from agents.run import Runner, RunConfig
from openai import AsyncOpenAI

from multi_agent.orchestrator_agent import orchestrator_agent
from multi_agent.technical_agent import technical_agent
from multi_agent.service_agent import comprehensive_service_agent
from multi_agent_langgraph.graph import run_langgraph_stream
from schemas.request import ChatMessageRequest
from services.session_service import session_service
from services.stream_response_service import process_stream_response
from utils.response_util import ResponseFactory
from infrastructure.logging.logger import logger
from schemas.response import ContentKind


class MultiAgentService:
    """
    多智能体业务服务类
    """

    @staticmethod
    def _build_runtime_model(request: ChatMessageRequest):
        cfg = request.runtime_model_config
        if not cfg or not cfg.base_url or not cfg.api_key or not cfg.model:
            return None

        try:
            client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
            return OpenAIChatCompletionsModel(model=cfg.model, openai_client=client)
        except Exception as e:
            logger.warning(f"运行时模型配置无效，将回退默认模型: {e}")
            return None

    @staticmethod
    def _build_runtime_orchestrator(runtime_model):
        if runtime_model is None:
            return orchestrator_agent

        return Agent(
            name=orchestrator_agent.name,
            instructions=orchestrator_agent.instructions,
            model=runtime_model,
            model_settings=ModelSettings(temperature=0),
            tools=orchestrator_agent.tools,
        )

    @classmethod
    async def process_task(cls, request: ChatMessageRequest, flag: bool) -> AsyncGenerator:
        """
        多智能体处理任务入口
        Args:
            request:  请求上下文

        Returns:
            AsyncGenerator：异步生成器对象（必须）
        """
        try:
            # 1. 获取请求上下文的信息
            user_id = request.context.user_id
            session_id = request.context.session_id
            user_query = request.query
            mode = request.mode or "agents"
            runtime_model = cls._build_runtime_model(request)

            # 2. 准备历史对话
            chat_history = session_service.prepare_history(user_id, session_id, user_query)

            # 3. 根据模式执行
            if mode == "langgraph":
                agent_result_parts = []
                async for chunk in run_langgraph_stream(
                    user_query=user_query,
                    messages=chat_history,
                ):
                    yield chunk
                    try:
                        import json
                        if chunk.startswith("data: "):
                            data = json.loads(chunk[6:].strip())
                            content = data.get("content", {})
                            if content.get("kind") == "ANSWER" and content.get("text"):
                                agent_result_parts.append(content["text"])
                    except Exception:
                        pass

                agent_result = "".join(agent_result_parts)
                if agent_result:
                    format_agent_result = re.sub(r'\n+', '\n', agent_result)
                    chat_history.append({"role": "assistant", "content": format_agent_result})
                    session_service.save_history(user_id, session_id, chat_history)
                return

            # 默认：OpenAI Agents SDK（严格超时 + 最多3次）
            max_retries = 3
            final_answer = ""
            final_error = ""
            runtime_orchestrator = cls._build_runtime_orchestrator(runtime_model)

            for attempt in range(1, max_retries + 1):
                retry_tip = f"⏱️ Orchestrator 尝试 {attempt}/{max_retries}"
                yield "data: " + ResponseFactory.build_text(
                    retry_tip, ContentKind.PROCESS
                ).model_dump_json() + "\n\n"

                try:
                    streaming_result = Runner.run_streamed(
                        starting_agent=runtime_orchestrator,
                        input=chat_history,
                        context=user_query,
                        max_turns=5,
                        run_config=RunConfig(tracing_disabled=True)
                    )

                    has_answer_chunk = False

                    # 改为稳态流式读取：避免 wait_for 触发取消传播，导致工具调用任务被强制 cancel
                    async for chunk in process_stream_response(streaming_result, emit_finish=False):
                        try:
                            import json
                            if chunk.startswith("data: "):
                                data = json.loads(chunk[6:].strip())
                                content = data.get("content", {})
                                if content.get("kind") == "ANSWER" and content.get("text"):
                                    has_answer_chunk = True
                        except Exception:
                            pass

                        yield chunk

                    agent_result = streaming_result.final_output
                    if agent_result is None:
                        agent_result = ""
                    elif not isinstance(agent_result, str):
                        agent_result = str(agent_result)
                    format_agent_result = re.sub(r'\n+', '\n', agent_result).strip()

                    if has_answer_chunk or format_agent_result:
                        final_answer = format_agent_result or "（已返回流式答案）"
                        # 关键修复：当模型没有产出流式 ANSWER 分片时，补发一次最终答案，避免前端只看到过程无结果
                        if not has_answer_chunk and format_agent_result:
                            yield "data: " + ResponseFactory.build_text(
                                format_agent_result, ContentKind.ANSWER
                            ).model_dump_json() + "\n\n"
                        break

                    raise RuntimeError("模型未产出可用回答")
                except Exception as e:
                    final_error = str(e)
                    yield "data: " + ResponseFactory.build_text(
                        f"⚠️ 本次执行异常：{final_error}", ContentKind.PROCESS
                    ).model_dump_json() + "\n\n"
                    logger.warning(f"第{attempt}次处理失败: {final_error}")

            if not final_answer:
                degrade_notice = (
                    "⚠️ Orchestrator 在 30s 超时/异常条件下已重试 3 次，现终止并降级。"
                    "你可稍后重试，或切换 Graph 架构。"
                )
                yield "data: " + ResponseFactory.build_text(
                    degrade_notice, ContentKind.DEGRADE
                ).model_dump_json() + "\n\n"

                fallback_answer = (
                    "当前请求失败，无法得到稳定回答。"
                    f"错误原因：{final_error or '未知错误'}"
                )
                yield "data: " + ResponseFactory.build_text(
                    fallback_answer, ContentKind.ANSWER
                ).model_dump_json() + "\n\n"
                final_answer = fallback_answer

            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

            chat_history.append({"role": "assistant", "content": final_answer})
            session_service.save_history(user_id, session_id, chat_history)
        except Exception as e:
            logger.error(f"AgentService.process_query执行出错: {str(e)}")
            logger.debug(f"异常详情: {traceback.format_exc()}")

            text = f"❌ 系统错误: {str(e)}"
            yield "data: " + ResponseFactory.build_text(
                text, ContentKind.PROCESS
            ).model_dump_json() + "\n\n"

            yield "data: " + ResponseFactory.build_text(
                "⚠️ 请求已终止：后端捕获到未处理异常。", ContentKind.DEGRADE
            ).model_dump_json() + "\n\n"

            yield "data: " + ResponseFactory.build_text(
                f"请求失败，错误原因：{str(e)}", ContentKind.ANSWER
            ).model_dump_json() + "\n\n"

            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
