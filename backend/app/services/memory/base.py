"""
Memory strategy protocol — all memory backends implement this interface.

采用策略模式：不同记忆后端共享同一接口，调用方无需知道具体实现。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class MemoryStrategy(ABC):
    """记忆策略基类，定义所有记忆后端必须实现的接口。"""

    @abstractmethod
    def prepare_history(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        max_turn: int = 3,
        memory_scope: str = "global",
    ) -> List[Dict[str, Any]]:
        """
        在发送给 LLM 之前，准备历史对话上下文。

        职责:
        - 加载短期会话记忆（当前会话的对话历史）
        - 注入长期记忆 / 语义记忆（如果后端支持）
        - 裁剪到合适的上下文窗口
        - 拼接当前用户输入

        Args:
            user_id: 用户唯一标识
            session_id: 会话 ID
            user_input: 用户当前输入
            max_turn: 保留的最大历史轮数
            memory_scope: 记忆范围 (global | session)

        Returns:
            发送给 LLM 的消息列表
        """
        ...

    @abstractmethod
    async def save_history(
        self,
        user_id: str,
        session_id: str,
        chat_history: List[Dict[str, Any]],
        memory_scope: str = "global",
    ):
        """
        保存对话历史，并从中提取长期记忆（如果后端支持）。

        Args:
            user_id: 用户唯一标识
            session_id: 会话 ID
            chat_history: 完整对话历史
            memory_scope: 记忆范围 (global | session)
        """
        ...

    @abstractmethod
    def delete_session(self, user_id: str, session_id: str) -> bool:
        """删除指定会话。"""
        ...

    @abstractmethod
    def get_all_sessions_memory(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有会话元数据列表。"""
        ...
