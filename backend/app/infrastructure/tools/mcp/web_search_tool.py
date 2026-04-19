"""
OpenAI Agents SDK 专用联网搜索工具

将 MCP 联网搜索封装为 @function_tool，供 technical_agent 直接调用。
"""
from agents import function_tool
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import search_mcp_client


@function_tool
async def web_search_tool(query: str) -> str:
    """
    联网搜索实时资讯，获取最新信息。

    适用于：天气预报、地震速报、新闻动态、科研成果、政策变动等实时信息。

    Args:
        query: 搜索关键词或问题

    Returns:
        str: 搜索结果文本
    """
    try:
        result = await search_mcp_client.call_tool(
            tool_name="bailian_web_search",
            arguments={"query": query},
        )
        if result and result.content:
            return result.content[0].text
        return "搜索未返回结果"
    except Exception as e:
        logger.error(f"web_search_tool error: {e}")
        return f"搜索失败: {str(e)}"
