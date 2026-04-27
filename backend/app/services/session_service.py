# 1. 优先import

from json import JSONDecodeError
from typing import List, Dict, Any

from repositories.session_repository import session_repository
from infrastructure.logging.logger import logger

# 2. 导入记忆策略
from services.memory.file_memory import file_memory, FileMemoryStrategy
from services.memory.mem0_memory import mem0_memory, Mem0MemoryStrategy

# 3. from 三方的


class SessionService:
    """
    会话业务管理服务类
    主要负责对用户历史会话的管理，包括
    1. 准备加载历史对话
    2. 读取历史对话
    3. 存储历史对话
    4. 查询会话列表

    采用策略模式支持不同记忆后端（file / mem0）。
    """

    DEFAULT_SESSION_ID = "default_session"

    # 记忆策略注册表
    _strategies = {
        "file": file_memory,
        "mem0": mem0_memory,
    }

    def __init__(self):
        """
        初始化会话操作的工具
        """
        self._repo = session_repository

    def _get_strategy(self, memory_mode: str):
        """根据记忆模式获取对应的策略。"""
        strategy = self._strategies.get(memory_mode, file_memory)
        return strategy

    def prepare_history(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        max_turn: int = 3,
        memory_mode: str = "file",
        memory_scope: str = "global",
    ) -> List[Dict[str, Any]]:
        """
        准备历史会话: 加载历史会话--->裁剪历史会话（保留指定轮数）--->返回历史会话
        调用的时机：发送请求给LLM之前(Agent运行之前)

        Args:
            user_id:  用户id
            session_id: 会话id
            user_input: 用户输入
            max_turn: 保留的最大轮数
            memory_mode: 记忆模式 (file | mem0)
            memory_scope: 记忆范围 (global | session)

        Returns:
            List[Dict[str, Any]]
        """
        strategy = self._get_strategy(memory_mode)
        return strategy.prepare_history(user_id, session_id, user_input, max_turn, memory_scope)

    def load_history(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        主要负责：加载历史会话（从文件中读取）
        Args:
            user_id: 用户id
            session_id: 会话id

        Returns:
            List[Dict[str, Any]]
        """
        # 1. 判断session_id是否为空
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID

        # 2. 加载
        try:
            session_history = self._repo.load_session(user_id, target_session_id)

            if session_history is None:
                # 构建一个新的结构（系统指令）
                return self._init_system_msg_instruct(target_session_id)
            return session_history
        except JSONDecodeError as e:
            logger.error(f"用户 {user_id}  会话 {session_id} 文件读取失败 原因 {e}")
            return [{"role": "system", "content": "用户历史的文件读取失败"}]

    async def save_history(
        self,
        user_id: str,
        session_id: str,
        chat_history: List[Dict[str, Any]],
        memory_mode: str = "file",
        memory_scope: str = "global",
    ):
        """
        保存历史会话
        调用的时机：调用完LLM（Agent）之后

        Args:
            user_id: 用户id
            session_id: 会话id
            chat_history: 要保存历史消息【角色：system/user/assistant】
            memory_mode: 记忆模式 (file | mem0)
            memory_scope: 记忆范围 (global | session)
        """
        strategy = self._get_strategy(memory_mode)
        await strategy.save_history(user_id, session_id, chat_history, memory_scope)

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """删除指定会话。

        Args:
            user_id: 用户唯一标识。
            session_id: 会话ID。

        Returns:
            bool: 删除成功返回 True，失败或不存在返回 False。
        """
        try:
            return self._repo.delete_session(user_id, session_id)
        except Exception as e:
            logger.error("删除用户 %s 会话 %s 失败: %s", user_id, session_id, str(e))
            return False

    def get_all_sessions_memory(self, user_id: str) -> List[Dict[str, Any]]:
        """获取并格式化用户的所有会话列表（用于前端侧边栏展示）。

        Args:
            user_id: 用户唯一标识。

        Returns:
            List[Dict]: 按创建时间倒序排列的会话列表。
        """
        # 1. 从 Repo 获取原始元数据
        raw_sessions = self._repo.get_all_sessions_metadata(user_id)

        formatted_sessions = []

        for session_id, create_time, data_or_error in raw_sessions:
            session_item = {
                "session_id": session_id,
                "create_time": create_time,
            }

            # 2. 处理可能的读取错误 (隔离异常，防止一个文件损坏导致整个列表挂掉)
            if isinstance(data_or_error, Exception):
                logger.error(
                    "读取会话 %s 失败: %s", session_id, str(data_or_error)
                )
                session_item.update({
                    "memory": [],
                    "total_messages": 0,
                    "error": "无法读取会话数据",
                })
            else:
                # 3. 正常数据处理：过滤 System 消息，只展示用户可见内容
                memory = data_or_error
                user_visible_memory = [
                    msg for msg in memory if msg.get("role") != "system"
                ]
                session_item.update({
                    "memory": user_visible_memory,
                    "total_messages": len(user_visible_memory),
                })

            formatted_sessions.append(session_item)

        # 4. 排序：按时间倒序（最新的在最前）
        formatted_sessions.sort(
            key=lambda x: x.get("create_time") or "",
            reverse=True
        )

        return formatted_sessions

    def _init_system_msg_instruct(self, session_id) -> List[Dict[str, Any]]:
        """
         初始化一个带系统角色的消息结构
        Args:
            session_id: 会话id

        Returns:
            List[Dict[str, Any]]
        """
        return [{
            "role": "system",
            "content": f"你是一个有记忆的智能体助手，请基于上下文历史会话用户问题 (会话ID {session_id})"
        }]

    def _truncate_history(self, chat_history: List[Dict[str, Any]], max_turn: int = 3) -> List[Dict[str, Any]]:
        """
        裁剪指定轮数的消息
        Args:
            chat_history: 加载到的历史对话消息
            max_turn: 指定最大轮数的历史消息

        Returns:
            List[Dict[str, Any]]：最近指定轮数的历史消息
        """
        # 1. 获取系统角色的消息[无论如何都要留，通常来说就一条]
        system_msg = [msg for msg in chat_history if msg.get('role') == 'system']

        # 2. 获取非系统角色的消息【user & assistant】
        no_system_msg = [msg for msg in chat_history if msg.get('role') != 'system']

        msg_limit = max_turn * 2  # (3轮)

        # 3. 裁剪非系统角色的消息列表
        truncate_msg = no_system_msg[-msg_limit:]

        # 4. 拼接上系统角色的消息
        final_msg = system_msg + truncate_msg

        # 5. 返回指定轮数的消息
        return final_msg


# 全局单例
session_service = SessionService()

if __name__ == '__main__':
    result1 = session_service.prepare_history("hzk", "666", "你好!")
    result1.append({"role": "assistant", "content": "您好，请问有什么可以帮助您嘛"})

    import asyncio
    asyncio.run(session_service.save_history("hzk", "666", result1))
