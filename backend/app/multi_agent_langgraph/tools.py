"""
LangGraph 工具封装模块

将底层基础设施工具封装为 LangChain @tool，供 ReAct agent 调用。
"""
from langchain_core.tools import tool

from infrastructure.tools.local.knowledge_base import query_knowledge_raw
from infrastructure.tools.local.service_station import (
    resolve_user_location_from_text_impl,
    query_nearest_repair_shops_by_coords_impl,
)
from infrastructure.tools.mcp.mcp_servers import search_mcp_client, baidu_mcp_client
from infrastructure.logging.logger import logger


# ---------------------------------------------------------------------------
# 技术类工具
# ---------------------------------------------------------------------------

@tool
async def knowledge_base_tool(question: str) -> str:
    """查询地质知识库，获取地质专业知识的权威解答。
    适用于：岩石鉴定、矿物识别、地层分析、构造特征等地质专业问题。"""
    try:
        result = await query_knowledge_raw(question=question)
        if isinstance(result, dict):
            if result.get("status") == "error":
                return f"知识库查询失败: {result.get('error_msg', '未知错误')}"
            if "answer" in result:
                return str(result["answer"])
        return str(result)
    except Exception as e:
        logger.error(f"knowledge_base_tool error: {e}")
        return f"知识库查询异常: {str(e)}"


@tool
async def web_search_tool(query: str) -> str:
    """联网搜索实时资讯，获取最新信息。
    适用于：天气预报、地震速报、新闻动态、科研成果、政策变动等实时信息。"""
    try:
        result = await search_mcp_client.call_tool(
            tool_name="bailian_web_search",
            arguments={"query": query},
        )
        return result.content[0].text
    except Exception as e:
        logger.error(f"web_search_tool error: {e}")
        return f"搜索失败: {str(e)}"


# ---------------------------------------------------------------------------
# 后勤导航类工具
# ---------------------------------------------------------------------------

@tool
async def resolve_location_tool(user_input: str) -> str:
    """解析用户位置信息，支持地址文本解析和IP定位。
    在查询附近站点前必须先调用此工具获取用户坐标。"""
    try:
        return await resolve_user_location_from_text_impl(user_input=user_input)
    except Exception as e:
        logger.error(f"resolve_location_tool error: {e}")
        return f"位置解析失败: {str(e)}"


@tool
def nearest_sites_tool(lat: float, lng: float, limit: int = 3) -> str:
    """根据坐标查询附近的野外站点（村庄、医疗站、补给点等）。
    需要先通过 resolve_location_tool 获取经纬度坐标。"""
    try:
        return query_nearest_repair_shops_by_coords_impl(lat=lat, lng=lng, limit=limit)
    except Exception as e:
        logger.error(f"nearest_sites_tool error: {e}")
        return f"站点查询失败: {str(e)}"


@tool
async def map_geocode_tool(address: str) -> str:
    """地理编码：将地址文本转换为经纬度坐标。"""
    try:
        result = await baidu_mcp_client.call_tool(
            tool_name="map_geocode",
            arguments={"address": address},
        )
        return result.content[0].text
    except Exception as e:
        logger.error(f"map_geocode_tool error: {e}")
        return f"地理编码失败: {str(e)}"


@tool
async def map_ip_location_tool(ip: str) -> str:
    """IP定位：根据IP地址获取大致地理位置。"""
    try:
        result = await baidu_mcp_client.call_tool(
            tool_name="map_ip_location",
            arguments={"ip": ip},
        )
        return result.content[0].text
    except Exception as e:
        logger.error(f"map_ip_location_tool error: {e}")
        return f"IP定位失败: {str(e)}"


@tool
async def map_uri_tool(service: str = "direction") -> str:
    """生成百度地图导航链接，用于路线规划。"""
    try:
        result = await baidu_mcp_client.call_tool(
            tool_name="map_uri",
            arguments={"service": service},
        )
        return result.content[0].text
    except Exception as e:
        logger.error(f"map_uri_tool error: {e}")
        return f"导航链接生成失败: {str(e)}"


# ---------------------------------------------------------------------------
# 工具分组
# ---------------------------------------------------------------------------

TECHNICAL_TOOLS = [knowledge_base_tool, web_search_tool]
SERVICE_TOOLS = [
    resolve_location_tool, nearest_sites_tool,
    map_geocode_tool, map_ip_location_tool, map_uri_tool,
]
ALL_TOOLS = [*TECHNICAL_TOOLS, *SERVICE_TOOLS]
