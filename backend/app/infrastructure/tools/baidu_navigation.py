"""
百度地图导航工具封装（带路线格式化）

问题：Baidu MCP 原始导航工具返回大量原始步骤数据（可能包含数百个重复路段），
LLM 直接将其逐条输出，导致用户看到几十条 "沿同一条路行驶X米" 的重复内容。

解决：在 Python 层调用 Baidu MCP，并对返回的路线步骤进行格式化后再交给 LLM。
"""
from __future__ import annotations

from agents import function_tool

from infrastructure.logging.logger import logger
from infrastructure.tools.local.route_formatter import format_route_steps, format_route_response


# ---------------------------------------------------------------------------
# 内部辅助：调用 Baidu MCP 工具
# ---------------------------------------------------------------------------
async def _call_baidu_mcp(tool_name: str, args: dict):
    """调用 Baidu MCP 并返回文本结果"""
    from infrastructure.tools.mcp.mcp_servers import baidu_mcp_client
    result = await baidu_mcp_client.call_tool(tool_name=tool_name, arguments=args)
    return result.content[0].text if result.content else ""


# ---------------------------------------------------------------------------
# 地理编码（带格式化）
# ---------------------------------------------------------------------------
@function_tool
async def baidu_geocode(address: str) -> str:
    """
    【地址转坐标】将地址文本转换为经纬度坐标。
    示例："北京市海淀区中关村大街29号" → "116.32, 39.99"
    """
    try:
        raw = await _call_baidu_mcp("map_geocode", {"address": address})
        return raw or f"未能解析地址: {address}"
    except Exception as e:
        logger.error(f"baidu_geocode error: {e}")
        return f"地理编码失败: {str(e)}"


# ---------------------------------------------------------------------------
# 反向地理编码（带格式化）
# ---------------------------------------------------------------------------
@function_tool
async def baidu_reverse_geocode(lat: float, lng: float) -> str:
    """
    【坐标转地址】将经纬度坐标转换为具体地址。
    """
    try:
        raw = await _call_baidu_mcp("map_reverse_geocode", {"lat": lat, "lng": lng})
        return raw or "未能解析坐标"
    except Exception as e:
        logger.error(f"baidu_reverse_geocode error: {e}")
        return f"反向地理编码失败: {str(e)}"


# ---------------------------------------------------------------------------
# 导航路线规划（核心：带路线格式化）
# ---------------------------------------------------------------------------
@function_tool
async def baidu_directions(
    origin: str,
    destination: str,
    origin_region: str = "北京",
    destination_region: str = "北京",
    mode: str = "driving",
) -> str:
    """
    【路线规划】规划从起点到终点的导航路线。

    Args:
        origin: 起点地址（如 "中国地质大学北京校区"）
        destination: 终点地址（如 "天安门"）
        origin_region: 起点所在城市（默认"北京"）
        destination_region: 终点所在城市（默认"北京"）
        mode: 导航方式（driving=驾车, walking=步行, transit=公交, riding=骑行）

    返回：格式化后的路线总览 + 关键转向步骤 + 导航链接
    """
    try:
        import json

        # 1. 地理编码：起点和终点 → 坐标
        origin_raw = await _call_baidu_mcp("map_geocode", {
            "address": origin,
            "region": origin_region,
        })
        dest_raw = await _call_baidu_mcp("map_geocode", {
            "address": destination,
            "region": destination_region,
        })

        origin_coords = _extract_coords(origin_raw)
        dest_coords = _extract_coords(dest_raw)

        if not origin_coords or not dest_coords:
            return (
                f"无法规划路线：未能获取起点或终点的坐标。\n"
                f"起点: {origin} ({origin_raw[:200]})\n"
                f"终点: {destination} ({dest_raw[:200]})\n"
                f"请提供更详细的地址信息。"
            )

        o_lng, o_lat = origin_coords
        d_lng, d_lat = dest_coords

        # 2. 调用路线规划
        raw_response = await _call_baidu_mcp("map_directions", {
            "origin": f"{o_lat},{o_lng}",
            "destination": f"{d_lat},{d_lng}",
            "mode": mode,
        })

        # 3. 格式化路线
        formatted = format_route_response(raw_response)

        # 4. 生成导航 URI
        try:
            uri_response = await _call_baidu_mcp("map_uri", {
                "service": "direction",
                "origin": f"{o_lat},{o_lng}",
                "destination": f"{d_lat},{d_lng}",
                "origin_region": origin_region,
                "destination_region": destination_region,
                "mode": mode,
            })
            uri = _extract_uri(uri_response)
            if uri:
                formatted += f"\n\n[点击打开百度地图导航]({uri})"
        except Exception:
            pass  # URI 生成失败不影响主结果

        return formatted

    except Exception as e:
        logger.error(f"baidu_directions error: {e}")
        return f"路线规划失败: {str(e)}"


# ---------------------------------------------------------------------------
# 导航 URI 生成（保持原有功能）
# ---------------------------------------------------------------------------
@function_tool
async def baidu_map_uri(
    origin: str = "",
    destination: str = "",
    mode: str = "driving",
) -> str:
    """
    【生成导航链接】生成百度地图导航 URI 链接。
    可单独使用，也可与 baidu_directions 配合。
    """
    try:
        args = {"service": "direction", "mode": mode}
        if origin:
            args["origin"] = origin
        if destination:
            args["destination"] = destination
        raw = await _call_baidu_mcp("map_uri", args)
        uri = _extract_uri(raw)
        if uri:
            return f"导航链接: {uri}"
        return raw or "未能生成导航链接"
    except Exception as e:
        logger.error(f"baidu_map_uri error: {e}")
        return f"导航链接生成失败: {str(e)}"


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------
def _extract_coords(text: str) -> tuple[float, float] | None:
    """从地理编码结果中提取经纬度"""
    import json
    import re

    text = text.strip()

    # 尝试解析 JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            result = data.get("result", {})
            location = result.get("location", {})
            lng = float(location.get("lng", 0))
            lat = float(location.get("lat", 0))
            if lng and lat:
                return (lng, lat)
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        pass

    # 尝试正则匹配
    match = re.search(r"(\d+\.?\d*)[,\s]+(\d+\.?\d*)", text)
    if match:
        return (float(match.group(1)), float(match.group(2)))

    return None


def _extract_uri(text: str) -> str | None:
    """从响应中提取 URI"""
    import re

    text = text.strip()

    # 尝试 JSON 解析
    try:
        import json
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("uri", data.get("url", data.get("result", {}).get("uri", None)))
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试正则匹配 URL
    match = re.search(r'(https?://[^\s"\'<>]+)', text)
    if match:
        return match.group(1)

    return None
