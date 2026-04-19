from contextlib import AsyncExitStack
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import (
    search_mcp_client,
    baidu_mcp_client,
)


class MCPSessionManager:
    """
    MCP 连接生命周期管理器。

    两种用法：
    1. 异步上下文管理器（推荐）：自动处理 connect/cleanup，适合 use_inside 场景
       async with MCPSessionManager() as mcp:
           await mcp.call(...)
    2. 手动 connect/cleanup（兼容旧接口）：显式控制生命周期
       await mcp.connect()
       try:
           ...
       finally:
           await mcp.cleanup()

    与 graph.py 中 AsyncExitStack 的做法对齐，
    统一替代 agent_factory.py 中 tool 函数内部的手动 connect/cleanup。
    """

    def __init__(self):
        self._stack: AsyncExitStack | None = None

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        await self._stack.enter_async_context(baidu_mcp_client)
        await self._stack.enter_async_context(search_mcp_client)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._stack:
            await self._stack.aclose()
        return False

    async def connect(self):
        """手动连接（兼容旧接口）。"""
        if self._stack is None:
            self._stack = AsyncExitStack()
            await self._stack.enter_async_context(baidu_mcp_client)
            await self._stack.enter_async_context(search_mcp_client)

    async def cleanup(self):
        """手动清理（兼容旧接口）。"""
        if self._stack:
            await self._stack.aclose()
            self._stack = None


# 全局管理器实例，供 agent_factory.py 使用
mcp_session_manager = MCPSessionManager()


# ---------------------------------------------------------------------------
# 以下为兼容旧接口，不推荐新代码使用
# ---------------------------------------------------------------------------

async def mcp_connect():
    """兼容旧接口，推荐使用 MCPSessionManager 上下文管理器。"""
    await mcp_session_manager.connect()


async def mcp_cleanup():
    """兼容旧接口，推荐使用 MCPSessionManager 上下文管理器。"""
    await mcp_session_manager.cleanup()