import asyncio

from fastapi.routing import APIRouter
from starlette.responses import StreamingResponse, JSONResponse

from schemas.request import (
    ChatMessageRequest, UserSessionsRequest, DeleteSessionRequest, CreateSessionRequest,
    HistoryRequest, ReplayRequest,
    MemoryListRequest, MemoryGetRequest, MemoryDeleteRequest,
    MemoryUpdateRequest, MemoryDeleteAllRequest, MemoryCleanupRequest, MemoryPromoteSessionRequest,
    SessionMessagesRequest, DeleteSessionMessageRequest,
)
from services.agent_service import MultiAgentService
from infrastructure.logging.logger import logger
from services.session_service import session_service
from multi_agent_langgraph.graph import (
    get_graph_state_history, replay_from_checkpoint,
    interrupt_and_wait_for_input, build_langgraph_app,
)
from infrastructure.tools.local.knowledge_base import query_knowledge_raw
from config.settings import settings

# 1. 定义请求路由器
router = APIRouter()


# 获取当前模型配置
@router.get("/api/model_config", summary="获取当前模型配置")
async def get_model_config():
    """
    返回当前系统使用的模型配置

    Returns:
        JSON格式的模型配置信息
    """
    try:
        # 从知识库服务获取向量模型配置
        import httpx
        embedding_model = "text-embedding-v3"  # 默认值

        try:
            async with httpx.AsyncClient() as client:
                kb_response = await client.get(
                    "http://127.0.0.1:8001/api/model_config",
                    timeout=2.0
                )
                if kb_response.status_code == 200:
                    kb_config = kb_response.json()
                    embedding_model = kb_config.get("embedding_model", embedding_model)
        except Exception as e:
            logger.warning(f"无法获取知识库模型配置: {e}")

        return JSONResponse({
            "success": True,
            "config": {
                "chat_model": settings.MAIN_MODEL_NAME or "Qwen/Qwen3-32B",
                "embedding_model": embedding_model,
                "base_url": settings.SF_BASE_URL or settings.AL_BAILIAN_BASE_URL,
            }
        })
    except Exception as e:
        logger.error(f"获取模型配置失败: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        })


# 记忆模式状态检查
@router.get("/api/memory_status", summary="获取记忆模式可用状态")
async def get_memory_status():
    """
    返回 mem0 记忆引擎的可用性状态。
    前端据此决定是否可以切换到 AI 记忆模式。
    """
    try:
        from services.memory.mem0_memory import mem0_memory
        status = mem0_memory.get_status()
        return JSONResponse({
            "success": True,
            "mem0": status,
        })
    except Exception as e:
        logger.error(f"获取记忆状态失败: {e}")
        return JSONResponse({
            "success": True,
            "mem0": {"available": False, "message": f"状态检查异常: {str(e)}"},
        })


# 2. 定义对话请求
@router.post("/api/query", summary="智能体对话接口")
async def query(request_context: ChatMessageRequest) -> StreamingResponse:
    """
    SSE返回数据（流式响应）
    响应头中：text/event-stream
    Args:
        request_context: 请求上下文

    Returns:
        StreamingResponse

    """

    # 1. 获取请求上下文的属性
    user_id = request_context.context.user_id
    user_query = request_context.query
    logger.info(f"用户 {user_id} 发送的待处理任务 {user_query}")

    async def safe_stream():
        try:
            async for chunk in MultiAgentService.process_task(request_context, flag=True):
                yield chunk
        except asyncio.CancelledError:
            # 客户端断开、页面刷新或前端主动取消时会触发；避免打出无意义长堆栈
            logger.warning(f"SSE连接已取消: user={user_id}, query={user_query}")
            return

    # 3. 封装结果到StreamingResponse中
    return StreamingResponse(
        content=safe_stream(),
        status_code=200,
        media_type="text/event-stream"
    )


# 知识仓智搜专用端点 - 直接查询RAG知识库，不走智能体编排
@router.post("/api/knowledge_query", summary="知识仓智搜接口")
async def knowledge_query(request_context: ChatMessageRequest):
    """
    直接查询RAG知识库，返回检索结果。
    所有回答都基于RAG召回的内容，适用于地质专业知识查询。

    Args:
        request_context: 请求上下文，包含query和context

    Returns:
        JSON格式的知识库查询结果
    """
    user_id = request_context.context.user_id
    user_query = request_context.query
    logger.info(f"[知识仓] 用户 {user_id} 查询: {user_query}")

    try:
        result = await query_knowledge_raw(question=user_query)

        if result.get("status") == "ok":
            answer = result.get("answer", "")
            if answer:
                return JSONResponse({
                    "success": True,
                    "answer": answer,
                    "question": user_query,
                })
            else:
                return JSONResponse({
                    "success": False,
                    "error": "知识库未返回有效答案",
                    "question": user_query,
                })
        else:
            error_msg = result.get("error_msg", "未知错误")
            return JSONResponse({
                "success": False,
                "error": f"知识库查询失败: {error_msg}",
                "question": user_query,
            })
    except Exception as e:
        logger.error(f"[知识仓] 查询异常: {repr(e)}")
        return JSONResponse({
            "success": False,
            "error": f"查询异常: {str(e)}",
            "question": user_query,
        })


@router.post("/api/user_sessions")
def get_user_sessions(request: UserSessionsRequest):
    """
    获取用户的所有会话记忆数据。

    Args:
        request: 包含 user_id 的请求体。

    Returns:
        包含用户所有会话信息和记忆的 JSON 响应。
    """
    # 1. 日志记录：记录请求到达
    logger.info("接收到获取用户会话请求")

    # 2. 参数提取：从请求模型中获取目标用户ID
    user_id = request.user_id
    logger.info(f"获取用户 {user_id} 的所有会话记忆数据")

    try:
        # 3. 服务调用 session_service 从底层存储检索所有历史会话
        all_sessions = session_service.get_all_sessions_memory(user_id)
        logger.debug(f"成功获取用户 {user_id} 的 {len(all_sessions)} 个会话")

        # 4. 响应构建：组装并返回标准化的成功 JSON 数据
        return {
            "success": True,
            "user_id": user_id,
            "total_sessions": len(all_sessions),
            "sessions": all_sessions
        }
    except Exception as e:
        # 5. 异常处理：捕获服务层抛出的未知错误，记录日志并返回错误标识
        logger.error(f"获取用户 {user_id} 的会话数据时出错: {str(e)}")
        return {
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }


@router.post("/api/delete_session")
def delete_user_session(request: DeleteSessionRequest):
    """删除用户指定历史会话。"""
    logger.info(f"接收到删除会话请求 user={request.user_id}, session={request.session_id}")

    if request.session_id == session_service.DEFAULT_SESSION_ID:
        return {
            "success": False,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "error": "默认会话不允许删除"
        }

    deleted = session_service.delete_session(request.user_id, request.session_id)

    return {
        "success": deleted,
        "user_id": request.user_id,
        "session_id": request.session_id,
        "message": "删除成功" if deleted else "会话不存在或删除失败"
    }


@router.post("/api/create_session")
def create_user_session(request: CreateSessionRequest):
    """创建新会话（在后端创建空会话文件，确保刷新后仍存在）。"""
    logger.info(f"[创建会话] user={request.user_id}, session={request.session_id}")
    try:
        import asyncio
        # 创建空会话文件（包含一个初始 system 消息）
        initial_data = [{"role": "system", "content": f"你是一个有记忆的智能体助手，请基于上下文历史会话用户问题 (会话ID {request.session_id})"}]
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            session_service.save_history(request.user_id, request.session_id, initial_data, memory_mode="file")
        )
        loop.close()
        return {
            "success": True,
            "user_id": request.user_id,
            "session_id": request.session_id,
        }
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/session_messages")
def get_session_messages(request: SessionMessagesRequest):
    """获取指定会话的所有消息（用于会话记忆面板展示）。"""
    logger.info(f"[会话记忆] user={request.user_id}, session={request.session_id}")
    try:
        from repositories.session_repository import session_repository
        target_session_id = request.session_id or session_service.DEFAULT_SESSION_ID
        messages = session_repository.load_session(request.user_id, target_session_id)
        if messages is None:
            messages = []
        # 过滤掉 process 角色
        messages = [m for m in messages if m.get("role") != "process"]
        return {
            "success": True,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "total": len(messages),
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/delete_session_message")
def delete_session_message(request: DeleteSessionMessageRequest):
    """删除会话中的单条消息（用于会话记忆面板逐条删除）。"""
    logger.info(f"[会话记忆] user={request.user_id} 删除消息 index={request.message_index}, session={request.session_id}")
    try:
        from repositories.session_repository import session_repository
        target_session_id = request.session_id or session_service.DEFAULT_SESSION_ID
        messages = session_repository.load_session(request.user_id, target_session_id)
        if messages is None:
            return {"success": False, "error": "会话不存在"}
        idx = request.message_index
        if idx < 0 or idx >= len(messages):
            return {"success": False, "error": f"索引 {idx} 越界，共 {len(messages)} 条消息"}
        deleted_msg = messages.pop(idx)
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            session_repository.save_session(request.user_id, target_session_id, messages)
        )
        loop.close()
        return {
            "success": True,
            "deleted_role": deleted_msg.get("role"),
            "deleted_content": deleted_msg.get("content", "")[:50],
        }
    except Exception as e:
        logger.error(f"删除会话消息失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================================
# LangGraph 原生能力 API（Checkpointing / History / Time Travel）
# ============================================================================

@router.post("/api/langgraph/history")
def get_execution_history(request: HistoryRequest):
    """
    获取指定会话的 LangGraph 执行历史（所有 checkpoint）。

    返回按时间顺序排列的状态快照列表，可用于：
    - 前端可视化展示完整的节点执行轨迹
    - 调试时查看任意历史状态
    - 实现"时间旅行"选择回溯点

    Args:
        request: 包含 user_id, session_id 的请求体

    Returns:
        所有 checkpoint 的列表（从旧到新）
    """
    thread_id = f"{request.user_id}:{request.session_id or session_service.DEFAULT_SESSION_ID}"

    try:
        checkpoints = get_graph_state_history(
            thread_id=thread_id,
            checkpoint_ns=request.user_id,
        )
        return {
            "success": True,
            "thread_id": thread_id,
            "total_checkpoints": len(checkpoints),
            "checkpoints": checkpoints,
        }
    except Exception as e:
        logger.error(f"获取执行历史失败: {e}")
        return {
            "success": False,
            "thread_id": thread_id,
            "error": str(e),
        }


@router.post("/api/langgraph/replay")
def replay_execution(request: ReplayRequest):
    """
    从指定 checkpoint 重新执行（时间旅行）。

    可用于：
    - 用户要求"重新回答"（从最新 checkpoint 重新）
    - 选择任意历史 checkpoint 回溯重做
    - 修复路径后继续执行

    Args:
        request: 包含 user_id, session_id, checkpoint_id 的请求体

    Returns:
        重新执行后的状态
    """
    thread_id = f"{request.user_id}:{request.session_id or session_service.DEFAULT_SESSION_ID}"

    try:
        result = replay_from_checkpoint(
            thread_id=thread_id,
            checkpoint_id=request.checkpoint_id,
            checkpoint_ns=request.user_id,
        )
        return {
            "success": True,
            "thread_id": thread_id,
            "checkpoint_id": request.checkpoint_id,
            "result": result,
        }
    except Exception as e:
        logger.error(f"重放执行失败: {e}")
        return {
            "success": False,
            "thread_id": thread_id,
            "error": str(e),
        }


@router.post("/api/langgraph/pause")
def pause_execution(request: HistoryRequest):
    """
    中断图执行并等待用户输入（Interrupt 模式）。

    当需要用户确认（如敏感操作、路径选择）时调用此接口，
    前端收到响应后展示"等待用户输入"状态，
    用户操作完成后通过 /api/langgraph/resume 继续执行。

    当前实现：返回 interrupt signal，实际中断由 NodeInterrupt 机制驱动。
    """
    thread_id = f"{request.user_id}:{request.session_id or session_service.DEFAULT_SESSION_ID}"

    try:
        signal = interrupt_and_wait_for_input(
            user_query=request.pause_message or "",
            thread_id=thread_id,
            checkpoint_ns=request.user_id,
        )
        return {
            "success": True,
            "thread_id": thread_id,
            "interrupt_signal": signal,
            "message": "图执行已暂停，等待用户输入",
        }
    except Exception as e:
        logger.error(f"暂停执行失败: {e}")
        return {
            "success": False,
            "thread_id": thread_id,
            "error": str(e),
        }


@router.post("/api/langgraph/resume")
def resume_execution(request: ReplayRequest):
    """
    从中断点继续执行（配合 /api/langgraph/pause 使用）。

    Args:
        request: 包含 user_id, session_id 和 resume_input（用户输入）

    Returns:
        继续执行后的状态
    """
    thread_id = f"{request.user_id}:{request.session_id or session_service.DEFAULT_SESSION_ID}"

    try:
        app = build_langgraph_app()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": request.user_id,
                "checkpoint_id": request.checkpoint_id,
            }
        }
        result = app.invoke(
            input={"resume": request.resume_input},
            config=config,
        )
        return {
            "success": True,
            "thread_id": thread_id,
            "result": result,
        }
    except Exception as e:
        logger.error(f"恢复执行失败: {e}")
        return {
            "success": False,
            "thread_id": thread_id,
            "error": str(e),
        }


# ============================================================================
# Mem0 记忆管理 API
# ============================================================================

@router.post("/api/memories/list")
async def list_user_memories(request: MemoryListRequest):
    """获取用户的 AI 记忆条目（支持按会话过滤）。"""
    try:
        from services.memory.mem0_memory import mem0_memory
        memories = await asyncio.wait_for(
            asyncio.to_thread(
                mem0_memory.get_all_memories,
                request.user_id,
                request.session_id,
                request.top_k,
            ),
            timeout=15,
        )
        return {
            "success": True,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "total": len(memories),
            "memories": memories,
        }
    except asyncio.TimeoutError:
        logger.error("memory list timeout")
        return {
            "success": False,
            "error": "memory list timeout: mem0/Chroma may be writing or locked by another process",
            "memories": [],
            "total": 0,
        }
    except Exception as e:
        logger.error(f"memory list failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "memories": [],
            "total": 0,
        }


@router.post("/api/memories/refining_status")
async def get_memory_refining_status(request: MemoryListRequest):
    """检查指定用户是否有正在进行的记忆精炼任务。"""
    try:
        memory_mode = request.memory_mode or "file"
        is_refining = False

        if memory_mode == "mem0":
            from services.memory.mem0_memory import mem0_memory
            is_refining = mem0_memory.is_refining(request.user_id)
        else:
            from services.memory.file_memory import file_memory
            is_refining = file_memory.is_refining(request.user_id)

        return {
            "success": True,
            "user_id": request.user_id,
            "is_refining": is_refining,
        }
    except Exception as e:
        logger.error(f"获取记忆精炼状态失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_refining": False,
        }


@router.post("/api/memories/get")
def get_memory_detail(request: MemoryGetRequest):
    """获取单条记忆的详情。"""
    try:
        from services.memory.mem0_memory import mem0_memory
        memory = mem0_memory.get_memory(request.memory_id, request.user_id)
        if memory:
            return {
                "success": True,
                "memory": memory,
            }
        return {
            "success": False,
            "error": "记忆不存在",
        }
    except Exception as e:
        logger.error(f"获取记忆详情失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/memories/delete")
def delete_single_memory(request: MemoryDeleteRequest):
    """删除单条记忆。"""
    logger.info(f"[记忆管理] 用户 {request.user_id} 删除记忆 {request.memory_id[:8]}...")
    try:
        from services.memory.mem0_memory import mem0_memory
        deleted = mem0_memory.delete_memory(request.user_id, request.memory_id)
        return {
            "success": deleted,
            "message": "删除成功" if deleted else "删除失败",
        }
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/memories/update")
def update_single_memory(request: MemoryUpdateRequest):
    """更新单条记忆的内容。"""
    logger.info(f"[记忆管理] 用户 {request.user_id} 更新记忆 {request.memory_id[:8]}...")
    try:
        from services.memory.mem0_memory import mem0_memory
        updated = mem0_memory.update_memory(request.user_id, request.memory_id, request.new_text)
        return {
            "success": updated,
            "message": "更新成功" if updated else "更新失败",
        }
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/memories/delete_all")
def delete_all_user_memories(request: MemoryDeleteAllRequest):
    """清空用户的 AI 记忆（支持按会话清空）。"""
    logger.info(f"[记忆管理] 用户 {request.user_id} 清空记忆, session={request.session_id}")
    try:
        from services.memory.mem0_memory import mem0_memory
        deleted_count = mem0_memory.delete_all_memories(request.user_id, request.session_id)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"已删除 {deleted_count} 条记忆",
        }
    except Exception as e:
        logger.error(f"清空记忆失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/memories/promote_session")
async def promote_session_memory(request: MemoryPromoteSessionRequest):
    """Promote a selected session transcript into global mem0 memory."""
    logger.info(
        f"[memory promote] user={request.user_id}, session={request.session_id}, "
        f"include_assistant={request.include_assistant}"
    )
    try:
        from services.memory.mem0_memory import mem0_memory
        result = await mem0_memory.promote_session_to_global(
            request.user_id,
            request.session_id,
            include_assistant=request.include_assistant,
            max_messages=request.max_messages,
        )
        return {
            "success": not result.get("error"),
            **result,
        }
    except Exception as e:
        logger.error(f"promote session memory failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/api/memories/cleanup")
def cleanup_expired_memories(request: MemoryCleanupRequest):
    """清理过期记忆（超过指定天数或超出数量上限）。"""
    logger.info(f"[记忆管理] 用户 {request.user_id} 清理过期记忆")
    try:
        from services.memory.mem0_memory import mem0_memory
        result = mem0_memory.cleanup_expired_memories(
            request.user_id,
            request.max_age_days,
            request.max_count,
        )
        return {
            "success": True,
            **result,
        }
    except Exception as e:
        logger.error(f"清理记忆失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }
