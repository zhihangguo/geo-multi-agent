"""
LangGraph 工具封装模块

将底层基础设施工具封装为 LangChain @tool，供 ReAct agent 调用。
"""
from langchain_core.tools import tool
import httpx

from infrastructure.tools.local.knowledge_base import query_knowledge_raw
from infrastructure.tools.local.service_station import (
    resolve_user_location_from_text_impl,
    query_nearest_repair_shops_by_coords_impl,
)
from infrastructure.tools.mcp.mcp_servers import search_mcp_client, baidu_mcp_client
from infrastructure.logging.logger import logger

AUTOPILOT_BASE_URL = "http://127.0.0.1:8002/autopilot"


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


# ---------------------------------------------------------------------------
# 自动驾驶评估类工具
# ---------------------------------------------------------------------------

@tool
async def query_autopilot_data_tool(question: str, tenant_id: str = "tenant_a") -> str:
    """查询自动驾驶测试数据。支持自然语言查询测试记录、感知指标、安全事件等。
    会自动将自然语言转为 SQL 并执行，返回结构化结果。
    适用于：统计查询（如"雨天测试的感知精确率"）、明细查询（如"AV-001 的所有测试"）、
           对比分析（如"城区和高速的表现差异"）、安全评分等。
    示例："上个月雨天场景的感知精确率和召回率如何"
    示例："AV-001 在城区道路的所有测试记录"
    示例:"哪个车队的表现最好" """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AUTOPILOT_BASE_URL}/query",
                json={"question": question, "tenant_id": tenant_id, "search_mode": "auto"},
            )
            result = resp.json()
        if result.get("success"):
            parts = []
            answer = result.get("answer", "")
            sql = result.get("sql", "")
            data = result.get("data", [])
            if answer:
                parts.append(answer)
            if sql:
                parts.append(f"\n执行的 SQL:\n{sql}")
            if data:
                parts.append(f"\n查询到 {len(data)} 条数据:")
                for row in data[:10]:
                    parts.append(f"  {row}")
                if len(data) > 10:
                    parts.append(f"  ... 还有 {len(data) - 10} 条")
            return "\n".join(parts) if parts else "查询成功，但无数据。"
        return f"查询失败: {result.get('error', '未知错误')}"
    except Exception as e:
        logger.error(f"query_autopilot_data_tool error: {e}")
        return f"查询异常: {str(e)}"


@tool
async def analyze_autopilot_logs_tool(run_id: str, tenant_id: str = "tenant_a") -> str:
    """分析自动驾驶系统日志。返回延迟分布、ERROR/WARNING 统计、性能瓶颈。
    适用于：分析某次测试运行中的系统表现和异常。
    示例："分析 RUN-001 的系统日志，看看有没有异常" """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AUTOPILOT_BASE_URL}/analyze",
                json={"run_id": run_id, "tenant_id": tenant_id, "analysis_type": "logs"},
            )
            result = resp.json()
        if result.get("success"):
            return result.get("content", "日志分析完成。")
        return f"分析失败: {result.get('error', '未知错误')}"
    except Exception as e:
        logger.error(f"analyze_autopilot_logs_tool error: {e}")
        return f"分析异常: {str(e)}"


@tool
async def generate_autopilot_report_tool(run_id: str, tenant_id: str = "tenant_a") -> str:
    """生成自动驾驶评估报告。包含感知评分、规划评分、安全评分、改进建议。
    示例：'生成 RUN-001 的评估报告'"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AUTOPILOT_BASE_URL}/report",
                json={"run_id": run_id, "tenant_id": tenant_id},
            )
            result = resp.json()
        if result.get("success"):
            return result.get("content", "报告生成完成。")
        return f"报告生成失败: {result.get('error', '未知错误')}"
    except Exception as e:
        logger.error(f"generate_autopilot_report_tool error: {e}")
        return f"生成异常: {str(e)}"


@tool
async def semantic_search_autopilot_tool(
    query: str,
    tenant_id: str = "tenant_a",
    scenario_type: str = None,
    weather: str = None,
) -> str:
    """用语义相似度搜索自动驾驶测试记录。返回最接近的测试案例元数据。
    适用于：查找与某个描述相似的测试场景（如"找类似急刹车的案例"）。
    注意：此工具返回的是语义相近的测试记录元数据，不适合做统计计算（如平均精确率、总分对比等）。
    如果需要统计数据、计算指标或对比分析，请使用 query_autopilot_data_tool。
    示例："找类似高速变道失败的测试案例"
    示例："搜索感知表现最差的几次测试" """
    try:
        where_filters = {}
        if scenario_type:
            where_filters["scenario_type"] = scenario_type
        if weather:
            where_filters["weather"] = weather
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AUTOPILOT_BASE_URL}/semantic",
                json={
                    "query": query,
                    "tenant_id": tenant_id,
                    "where_filters": where_filters if where_filters else None,
                    "n_results": 10,
                },
            )
            # 检查 HTTP 状态码
            if resp.status_code != 200:
                return f"语义搜索失败: 服务器返回 {resp.status_code}。请确认向量库已同步。"
            result = resp.json()
        if result.get("success"):
            docs = result.get("results", [])
            if not docs:
                return "未找到匹配的测试结果。建议调整查询关键词或尝试 query_autopilot_data_tool 进行 Text2SQL 查询。"
            output = [f"找到 {len(docs)} 条相关记录:\n"]
            for i, doc in enumerate(docs):
                meta = doc.get("metadata", {})
                output.append(f"{i+1}. [{meta.get('table', 'unknown')}] {meta.get('run_id', '')}")
                for k, v in meta.items():
                    if k not in ("table", "run_id", "tenant_id", "_synced_at"):
                        output.append(f"   - {k}: {v}")
            return "\n".join(output)
        return f"搜索失败: {result.get('error', '未知错误')}"
    except httpx.HTTPError as e:
        return f"语义搜索网络错误: 无法连接 8002 端口的自动驾驶微服务。请确认服务已启动。"
    except Exception as e:
        logger.error(f"semantic_search_autopilot_tool error: {e}")
        return f"搜索异常: {str(e)}"


AUTOPILOT_TOOLS = [
    query_autopilot_data_tool,
    analyze_autopilot_logs_tool,
    generate_autopilot_report_tool,
    semantic_search_autopilot_tool,
]

ALL_TOOLS = [*TECHNICAL_TOOLS, *SERVICE_TOOLS, *AUTOPILOT_TOOLS]
