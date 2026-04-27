import asyncio
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
from infrastructure.tools.mcp.mcp_manager import MCPSessionManager


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
        # 声明在 try/finally 外层，确保 finally 块可访问
        user_id = request.context.user_id
        session_id = request.context.session_id
        user_query = request.query
        mode = request.mode or "agents"
        memory_mode = request.memory_mode or "file"
        memory_scope = request.memory_scope or "global"
        runtime_model = cls._build_runtime_model(request)

        # 准备 LLM 上下文（截断版）
        chat_history_for_llm = session_service.prepare_history(
            user_id, session_id, user_query,
            memory_mode=memory_mode, memory_scope=memory_scope,
        )
        # 加载完整历史用于保存（不截断）
        full_history = session_service.load_history(user_id, session_id)
        if full_history is None:
            full_history = [{"role": "system", "content": f"你是一个有记忆的智能体助手 (会话 {session_id or 'default'})"}]
        full_history.append({"role": "user", "content": user_query})

        final_answer = ""
        process_logs = []

        try:
            if mode == "langgraph":
                target_session_id = session_id or session_service.DEFAULT_SESSION_ID
                thread_id = f"{user_id}:{target_session_id}"

                agent_result_parts = []
                process_logs = []
                async with MCPSessionManager():
                    async for chunk in run_langgraph_stream(
                        user_query=user_query,
                        messages=chat_history_for_llm,
                        thread_id=thread_id,
                        checkpoint_ns=user_id,
                    ):
                        yield chunk
                        try:
                            import json
                            if chunk.startswith("data: "):
                                data = json.loads(chunk[6:].strip())
                                content = data.get("content", {})
                                kind = content.get("kind")
                                text = content.get("text", "")

                                if kind == "ANSWER" and text:
                                    agent_result_parts.append(text)
                                elif kind in ["THINKING", "PROCESS"] and text:
                                    process_logs.append(text)
                        except Exception:
                            pass

                agent_result = "".join(agent_result_parts)
                format_agent_result = re.sub(r'\n+', '\n', agent_result).strip() if agent_result else "（LangGraph 执行完成，但未产生回答）"
                final_answer = format_agent_result
                return

            # 默认：OpenAI Agents SDK
            max_retries = 3
            final_error = ""
            runtime_orchestrator = cls._build_runtime_orchestrator(runtime_model)

            async with MCPSessionManager():
                for attempt in range(1, max_retries + 1):
                    retry_tip = f"\u23f1\ufe0f Orchestrator 尝试 {attempt}/{max_retries}"
                    yield "data: " + ResponseFactory.build_text(
                        retry_tip, ContentKind.PROCESS
                    ).model_dump_json() + "\n\n"
                    process_logs.append(retry_tip)

                    try:
                        streaming_result = Runner.run_streamed(
                            starting_agent=runtime_orchestrator,
                            input=chat_history_for_llm,
                            context=user_query,
                            max_turns=8,
                            run_config=RunConfig(tracing_disabled=True)
                        )

                        has_answer_chunk = False
                        has_thinking_chunk = False

                        async for chunk in process_stream_response(streaming_result, emit_finish=False):
                            try:
                                import json
                                if chunk.startswith("data: "):
                                    data = json.loads(chunk[6:].strip())
                                    content = data.get("content", {})
                                    kind = content.get("kind")
                                    text = content.get("text", "")

                                    if kind == "THINKING" and text:
                                        has_thinking_chunk = True
                                        process_logs.append(text)

                                    if kind == "PROCESS" and text:
                                        process_logs.append(text)

                                    if kind == "ANSWER" and text:
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

                        # 安全网：如果没有 ANSWER chunk但 final_output 有内容，接受为有效回答
                        if has_answer_chunk or format_agent_result:
                            final_answer = format_agent_result or "（已返回流式答案）"
                            if not has_answer_chunk and format_agent_result:
                                yield "data: " + ResponseFactory.build_text(
                                    format_agent_result, ContentKind.ANSWER
                                ).model_dump_json() + "\n\n"
                            break

                        # 如果模型有思考内容但没产出 ANSWER，也作为降级接受
                        # 这通常发生在 reasoning 模型的思考模式未正确关闭时
                        if has_thinking_chunk and not format_agent_result:
                            logger.warning(f"模型仅产生 THINKING 内容但无 ANSWER，将思考内容作为回答输出")
                            final_answer = "\n".join([l for l in process_logs if l.strip()]) or ""
                            if final_answer:
                                yield "data: " + ResponseFactory.build_text(
                                    final_answer, ContentKind.ANSWER
                                ).model_dump_json() + "\n\n"
                                break

                        raise RuntimeError("模型未产出可用回答")
                    except Exception as e:
                        final_error = str(e)
                        yield "data: " + ResponseFactory.build_text(
                            f"\u26a0\ufe0f 本次执行异常：{final_error}", ContentKind.PROCESS
                        ).model_dump_json() + "\n\n"
                        logger.warning(f"第{attempt}次处理失败: {final_error}")

            if not final_answer:
                degrade_notice = (
                    "\u26a0\ufe0f Orchestrator 在 30s 超时/异常条件下已重试 3 次，现终止并降级。"
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

        except asyncio.CancelledError:
            # SSE 连接被取消（客户端断开/超时），也需要保存已有内容
            logger.info(f"请求被取消，但将保存已有内容: user={user_id}, session={session_id}")
            # 不重新抛出，让 finally 执行保存
        except Exception as e:
            logger.error(f"AgentService.process_query执行出错: {str(e)}")
            logger.debug(f"异常详情: {traceback.format_exc()}")

            text = f"\u274c 系统错误: {str(e)}"
            yield "data: " + ResponseFactory.build_text(
                text, ContentKind.PROCESS
            ).model_dump_json() + "\n\n"

            yield "data: " + ResponseFactory.build_text(
                "\u26a0\ufe0f 请求已终止：后端捕获到未处理异常。", ContentKind.DEGRADE
            ).model_dump_json() + "\n\n"

            yield "data: " + ResponseFactory.build_text(
                f"请求失败，错误原因：{str(e)}", ContentKind.ANSWER
            ).model_dump_json() + "\n\n"

            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

            # 即使异常，也保存已有内容到 finally

        finally:
            # 无论如何都保存会话历史（确保不丢失对话）
            if process_logs:
                process_content = "\n".join(process_logs)
                full_history.append({"role": "process", "content": process_content})

            if final_answer:
                full_history.append({"role": "assistant", "content": final_answer})

            if full_history:
                await session_service.save_history(
                    user_id, session_id, full_history,
                    memory_mode=memory_mode, memory_scope=memory_scope,
                )
                logger.info(f"会话历史已保存: user={user_id}, session={session_id}, 共{len(full_history)}条消息")
