"""
File-based memory strategy — the current JSON file session system.

This is the default, existing behavior wrapped in the MemoryStrategy interface.
"""
from json import JSONDecodeError
from typing import List, Dict, Any

from infrastructure.logging.logger import logger
from repositories.session_repository import session_repository
from services.memory.base import MemoryStrategy


class FileMemoryStrategy(MemoryStrategy):
    """
    基于 JSON 文件的记忆策略。
    封装现有的 SessionRepository 能力，保持向后兼容。
    """

    DEFAULT_SESSION_ID = "default_session"

    def __init__(self):
        self._repo = session_repository
        # 后台精炼任务跟踪（与 mem0_memory 保持一致）
        self._refining_tasks: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # MemoryStrategy 接口实现
    # ------------------------------------------------------------------

    def prepare_history(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        max_turn: int = 3,
        memory_scope: str = "global",
    ) -> List[Dict[str, Any]]:
        chat_history = self._load_history(user_id, session_id)
        if memory_scope == "global":
            memory_inject = self._build_global_memory_context(user_id, session_id, user_input)
            if memory_inject:
                system_msgs = [m for m in chat_history if m.get("role") == "system"]
                other_msgs = [m for m in chat_history if m.get("role") != "system"]
                chat_history = system_msgs + [memory_inject] + other_msgs
        chat_history.append({"role": "user", "content": user_input})
        return self._truncate_history(chat_history, max_turn)

    def _build_global_memory_context(self, user_id: str, session_id: str, user_input: str):
        """Load mem0 global memory before answering while keeping file session history."""
        try:
            from services.memory.mem0_memory import mem0_memory
        except ImportError:
            return None

        if not mem0_memory.is_available():
            return None

        return mem0_memory.build_memory_context_message(
            user_id=user_id,
            session_id=session_id,
            user_input=user_input,
            memory_scope="global",
        )

    async def save_history(
        self,
        user_id: str,
        session_id: str,
        chat_history: List[Dict[str, Any]],
        memory_scope: str = "global",
    ):
        if chat_history is None:
            return
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        try:
            await self._repo.save_session(user_id, target_session_id, chat_history)
        except Exception as e:
            logger.error(f"保存用户 {user_id} 会话 {session_id} 文件失败:{str(e)}")
            return

        # 全局模式下，异步提取到 mem0 长期记忆（fire-and-forget，不阻塞）
        if memory_scope == "global":
            try:
                from services.memory.mem0_memory import mem0_memory
            except ImportError:
                return
            if not mem0_memory.is_available():
                return

            payloads = mem0_memory._build_memory_write_payloads(chat_history)
            if not payloads:
                return

            import asyncio
            task = asyncio.create_task(
                mem0_memory._refine_or_save(user_id, target_session_id, payloads, memory_scope="global")
            )
            self._refining_tasks[user_id] = task

            def _untrack_task(t):
                try:
                    t.result()
                except Exception as e:
                    logger.error(f"[file_memory] 后台任务异常: {repr(e)}")
                finally:
                    self._refining_tasks.pop(user_id, None)

            task.add_done_callback(_untrack_task)

    def _extract_to_mem0(self, user_id: str, session_id: str, chat_history: List[Dict[str, Any]]):
        """同步回退路径（event loop 不可用时调用）。"""
        try:
            from services.memory.mem0_memory import mem0_memory
        except ImportError:
            return
        if not mem0_memory.is_available():
            return

        payloads = mem0_memory._build_memory_write_payloads(chat_history)
        if not payloads:
            return
        # 同步走 LLM 提炼路径
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                mem0_memory._refine_or_save(user_id, session_id, payloads, memory_scope="global")
            )
        finally:
            loop.close()

    async def _extract_to_mem0_async(self, user_id: str, session_id: str, chat_history: List[Dict[str, Any]]):
        """异步路径：后台 LLM 提炼 + 保存（不阻塞 SSE 响应）。"""
        try:
            from services.memory.mem0_memory import mem0_memory
        except ImportError:
            return
        if not mem0_memory.is_available():
            return

        payloads = mem0_memory._build_memory_write_payloads(chat_history)
        if not payloads:
            return

        await mem0_memory._refine_or_save(user_id, session_id, payloads, memory_scope="global")

    def is_refining(self, user_id: str) -> bool:
        """检查该用户是否有活跃的后台记忆精炼任务。"""
        task = self._refining_tasks.get(user_id)
        if task is None:
            return False
        return not task.done()

    def delete_session(self, user_id: str, session_id: str) -> bool:
        try:
            return self._repo.delete_session(user_id, session_id)
        except Exception as e:
            logger.error("删除用户 %s 会话 %s 失败: %s", user_id, session_id, str(e))
            return False

    def get_all_sessions_memory(self, user_id: str) -> List[Dict[str, Any]]:
        raw_sessions = self._repo.get_all_sessions_metadata(user_id)
        formatted_sessions = []

        for sid, create_time, data_or_error in raw_sessions:
            session_item = {"session_id": sid, "create_time": create_time}

            if isinstance(data_or_error, Exception):
                logger.error("读取会话 %s 失败: %s", sid, str(data_or_error))
                session_item.update({
                    "memory": [],
                    "total_messages": 0,
                    "error": "无法读取会话数据",
                })
            else:
                memory = data_or_error
                user_visible_memory = [
                    msg for msg in memory if msg.get("role") != "system"
                ]
                session_item.update({
                    "memory": user_visible_memory,
                    "total_messages": len(user_visible_memory),
                })

            formatted_sessions.append(session_item)

        formatted_sessions.sort(
            key=lambda x: x.get("create_time") or "",
            reverse=True,
        )
        return formatted_sessions

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _load_history(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        try:
            session_history = self._repo.load_session(user_id, target_session_id)
            if session_history is None:
                return self._init_system_msg(target_session_id)
            return session_history
        except JSONDecodeError as e:
            logger.error(f"用户 {user_id}  会话 {session_id} 文件读取失败 原因 {e}")
            return [{"role": "system", "content": "用户历史的文件读取失败"}]

    def _init_system_msg(self, session_id: str) -> List[Dict[str, Any]]:
        return [{
            "role": "system",
            "content": f"你是一个有记忆的智能体助手，请基于上下文历史会话用户问题 (会话ID {session_id})"
        }]

    def _truncate_history(
        self,
        chat_history: List[Dict[str, Any]],
        max_turn: int = 3,
    ) -> List[Dict[str, Any]]:
        # 过滤掉 process 角色（思考过程日志），不应该发给 LLM
        valid_roles = {"system", "user", "assistant"}
        chat_history = [msg for msg in chat_history if msg.get("role") in valid_roles]

        system_msg = [msg for msg in chat_history if msg.get("role") == "system"]
        no_system_msg = [msg for msg in chat_history if msg.get("role") != "system"]
        msg_limit = max_turn * 2
        truncate_msg = no_system_msg[-msg_limit:]
        return system_msg + truncate_msg


# 全局单例
file_memory = FileMemoryStrategy()
