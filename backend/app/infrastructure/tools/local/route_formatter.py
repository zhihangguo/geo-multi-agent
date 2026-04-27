"""
导航路线格式化工具

问题：百度 MCP 返回的路线步骤可能包含大量重复或细碎的路段
（如连续数十次 "沿同一条路行驶X米，右转进入同一条路"）。

解决：在将路线数据交给 LLM 之前，先进行后处理：
1. 合并同一路段的连续步骤
2. 过滤过短的微小区段（<50m）
3. 限制输出步骤数量
"""


def format_route_steps(steps: list[dict], max_steps: int = 12) -> str:
    """
    将原始路线步骤列表格式化为简洁的导航指引。

    Args:
        steps: 每个步骤是一个 dict，预期包含:
            - instruction: 导航指令文本（如 "沿中关村北大街行驶"）
            - distance: 距离（米）
            - duration: 耗时（秒）
            - road: 道路名称（可能从 instruction 中提取）
        max_steps: 最多返回的步骤数

    Returns:
        格式化后的路线文本
    """
    if not steps:
        return "未获取到详细路线步骤。"

    # 1. 提取道路名称（从 instruction 中解析 "沿XX行驶" 模式）
    import re

    def extract_road(instruction: str) -> str:
        """从导航指令中提取主要道路名"""
        # 匹配 "沿XXX行驶" 模式
        m = re.search(r"沿(.+?)行驶", instruction)
        if m:
            return m.group(1).strip()
        # 匹配 "进入XXX" 模式
        m = re.search(r"进入(.+?)(?:[,，]|$)", instruction)
        if m:
            return m.group(1).strip()
        # 匹配 "XX路", "XX街", "XX大道" 等
        m = re.search(r"([\u4e00-\u9fa5]+(?:路|街|大道|巷|桥|环岛|高速))", instruction)
        if m:
            return m.group(1).strip()
        return ""

    # 2. 预处理：为每个步骤提取道路名
    for step in steps:
        instr = step.get("instruction", "") or step.get("navi_info", "") or str(step)
        step["_instruction"] = instr
        step["_road"] = extract_road(instr)
        step["_distance"] = float(step.get("distance", 0) or 0)
        step["_duration"] = float(step.get("duration", 0) or 0)

    # 3. 合并同一路段的连续步骤
    merged = []
    current = None

    for step in steps:
        road = step["_road"]
        dist = step["_distance"]
        dur = step["_duration"]
        instr = step["_instruction"]

        # 如果道路名为空或步骤没有有效导航信息，跳过
        if not road and dist < 50:
            continue

        if current is None:
            current = {
                "road": road,
                "instruction": instr,
                "distance": dist,
                "duration": dur,
                "steps_merged": 1,
            }
            continue

        # 同一道路 → 合并
        if road and road == current["road"]:
            current["distance"] += dist
            current["duration"] += dur
            current["steps_merged"] += 1
            # 保留最后一个指令（通常是最准确的转向指令）
            if instr:
                current["instruction"] = instr
        else:
            # 不同道路 → 保存当前，开始新的
            merged.append(current)
            current = {
                "road": road,
                "instruction": instr,
                "distance": dist,
                "duration": dur,
                "steps_merged": 1,
            }

    if current:
        merged.append(current)

    # 4. 过滤过短的步骤（<30m 的微小区段，合并到相邻步骤）
    filtered = []
    for m in merged:
        if m["distance"] >= 30 or m["road"]:
            filtered.append(m)
        elif filtered:
            # 合并到前一个步骤
            filtered[-1]["distance"] += m["distance"]
            filtered[-1]["duration"] += m["duration"]

    # 5. 格式化输出
    total_distance = sum(m["distance"] for m in filtered)
    total_duration = sum(m["duration"] for m in filtered)

    lines = [
        f"路线总览：全程约 {total_distance / 1000:.2f} 公里，预计 {int(total_duration / 60)} 分钟。",
        "",
        "详细步骤：",
    ]

    display_steps = filtered[:max_steps]
    for i, m in enumerate(display_steps, 1):
        dist_str = f"{m['distance']:.0f}米" if m["distance"] < 1000 else f"{m['distance']/1000:.2f}公里"
        instr = m["instruction"] or f"沿{m['road']}行驶"

        if m["steps_merged"] > 1:
            # 合并过多个步骤，简化描述
            # 提取转向动作
            turn_match = re.search(r"(右转|左转|直行|掉头|进入|驶向|上|下)[^,，]*", instr)
            if turn_match and m["road"]:
                action = turn_match.group(0)
                lines.append(f"  {i}. 沿{m['road']}行驶{dist_str}，{action}（合并 {m['steps_merged']} 个路段）")
            else:
                lines.append(f"  {i}. {instr}（{dist_str}，合并 {m['steps_merged']} 个路段）")
        else:
            lines.append(f"  {i}. {instr}（{dist_str}）")

    if len(filtered) > max_steps:
        remaining = len(filtered) - max_steps
        lines.append(f"  ... 还有 {remaining} 个路段，请在导航中查看完整路线。")

    return "\n".join(lines)


def format_route_response(raw_response: str) -> str:
    """
    尝试从原始导航响应中提取步骤并格式化。

    如果 raw_response 是 JSON 字符串，尝试解析并格式化。
    否则直接返回（可能已经是格式化的文本）。
    """
    import json

    raw_response = raw_response.strip()

    # 尝试解析 JSON
    try:
        data = json.loads(raw_response)
    except (json.JSONDecodeError, ValueError):
        # 不是 JSON，可能是已经格式化的文本
        # 检查是否有大量重复的 "沿...行驶" 模式
        import re
        segments = re.findall(r"沿.{1,30}行驶\d+米", raw_response)
        if len(segments) > 15:
            # 存在大量重复步骤，尝试简单去重
            return _simple_deduplicate(raw_response)
        return raw_response

    # 如果是百度 MCP 的标准响应格式
    if isinstance(data, dict):
        # 尝试不同可能的字段名
        steps = (
            data.get("result", {}).get("routes", [{}])[0].get("steps", [])
            if isinstance(data.get("result"), dict)
            else data.get("steps", data.get("routes", []))
        )

        if isinstance(steps, list) and len(steps) > 0:
            return format_route_steps(steps)

        # 如果有 content/text 字段，可能是文本响应
        content = data.get("content", data.get("text", data.get("message", "")))
        if content:
            return _simple_deduplicate(str(content)) if len(str(content)) > 500 else str(content)

    # 如果是数组
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], dict):
            return format_route_steps(data)

    # 兜底：转字符串返回
    return str(data)


def _simple_deduplicate(text: str, max_lines: int = 15) -> str:
    """
    对已格式化为文本的路线进行简单去重。
    当连续多行描述同一条道路时，合并它们。
    """
    import re

    lines = text.strip().split("\n")
    if len(lines) <= max_lines:
        return text

    merged_lines = []
    current_road = ""
    current_count = 0
    current_total_dist = 0

    for line in lines:
        match = re.search(r"沿(.+?)行驶(\d+)米", line)
        if match:
            road = match.group(1)
            dist = int(match.group(2))
            if road == current_road:
                current_count += 1
                current_total_dist += dist
            else:
                if current_road and current_count > 1:
                    merged_lines.append(
                        f"  - 沿{current_road}累计行驶{current_total_dist}米（{current_count}段合并）"
                    )
                current_road = road
                current_count = 1
                current_total_dist = dist
                merged_lines.append(line)
        else:
            if current_road and current_count > 1:
                merged_lines.append(
                    f"  - 沿{current_road}累计行驶{current_total_dist}米（{current_count}段合并）"
                )
                current_road = ""
                current_count = 0
                current_total_dist = 0
            merged_lines.append(line)

    # 处理最后一段
    if current_road and current_count > 1:
        merged_lines.append(
            f"  - 沿{current_road}累计行驶{current_total_dist}米（{current_count}段合并）"
        )

    # 如果还是太多，截断
    if len(merged_lines) > max_lines + 5:
        merged_lines = merged_lines[: max_lines + 2]
        merged_lines.append("  ... 更多路段请在导航中查看。")

    return "\n".join(merged_lines)
