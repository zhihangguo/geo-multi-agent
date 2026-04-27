"""
自动驾驶评估 Agent 工具集

工具通过 HTTP 调用 autopilot 微服务（port 8002）
"""
import httpx

from agents import function_tool

AUTOPILOT_BASE_URL = "http://127.0.0.1:8002/autopilot"


@function_tool
async def query_autopilot_data(question: str, tenant_id: str = "tenant_a") -> str:
    """
    【查询自动驾驶数据】自然语言查询自动驾驶数据库。
    支持：测试记录查询、感知指标统计、安全事件分析、多表联查。
    示例：'查询 AV-001 上个月所有雨天测试的感知精确率'
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AUTOPILOT_BASE_URL}/query",
            json={"question": question, "tenant_id": tenant_id, "search_mode": "auto"},
        )
        result = resp.json()

    if result.get("success"):
        answer = result.get("answer", "")
        data = result.get("data", [])
        mode = result.get("mode", "")
        sql = result.get("sql", "")

        output_parts = []
        if answer:
            output_parts.append(answer)
        if sql and mode == "text2sql":
            output_parts.append(f"\n执行的 SQL:\n```sql\n{sql}\n```")
        if data and len(data) <= 20:
            output_parts.append(f"\n查询结果 ({len(data)} 条):\n")
            for i, row in enumerate(data):
                row_str = ", ".join(f"{k}={v}" for k, v in row.items())
                output_parts.append(f"  {i+1}. {row_str}")
        elif data:
            output_parts.append(f"\n查询结果共 {len(data)} 条（仅展示前 10 条）")

        return "\n".join(output_parts)
    else:
        return f"查询失败: {result.get('error', '未知错误')}"


@function_tool
async def analyze_driving_logs(run_id: str, tenant_id: str = "tenant_a") -> str:
    """
    【分析驾驶日志】分析指定测试任务的系统日志。
    返回：模块延迟分布、ERROR/WARNING 统计、性能瓶颈识别。
    示例：'分析 RUN-001 的系统日志'
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AUTOPILOT_BASE_URL}/analyze",
            json={
                "run_id": run_id,
                "tenant_id": tenant_id,
                "analysis_type": "logs",
            },
        )
        result = resp.json()

    if result.get("success"):
        return result.get("content", "日志分析完成，但未返回内容。")
    return f"日志分析失败: {result.get('error', '未知错误')}"


@function_tool
async def get_safety_statistics(
    tenant_id: str = "tenant_a",
    vehicle_id: str | None = None,
    scenario_type: str | None = None,
    severity: str | None = None,
) -> str:
    """
    【安全事件统计】统计安全事件数据。
    支持按：车辆、场景类型、严重程度过滤。
    示例：'统计 AV-001 的所有高严重级别安全事件'
    """
    filters = {}
    if vehicle_id:
        filters["vehicle_id"] = vehicle_id
    if scenario_type:
        filters["scenario_type"] = scenario_type
    if severity:
        filters["severity"] = severity

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AUTOPILOT_BASE_URL}/stats",
            json={
                "run_id": "all",
                "tenant_id": tenant_id,
                "analysis_type": "safety",
                "filters": filters,
            },
        )
        result = resp.json()

    if result.get("success"):
        return result.get("content", "统计完成，但未返回内容。")
    return f"统计失败: {result.get('error', '未知错误')}"


@function_tool
async def generate_evaluation_report(run_id: str, tenant_id: str = "default") -> str:
    """
    【生成评估报告】为指定测试任务生成综合评估报告。
    包含：感知评分、规划评分、安全评分、改进建议。
    示例：'生成 RUN-001 的评估报告'
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AUTOPILOT_BASE_URL}/report",
            json={"run_id": run_id, "tenant_id": tenant_id},
        )
        result = resp.json()

    if result.get("success"):
        return result.get("content", "报告生成完成，但未返回内容。")
    return f"报告生成失败: {result.get('error', '未知错误')}"


@function_tool
async def sync_data_to_vector(
    table_name: str | None = None,
    tenant_id: str = "tenant_a",
    incremental: bool = False,
) -> str:
    """
    【同步数据到向量库】将 MySQL 指定表的数据同步到向量数据库。
    支持全量同步和增量同步。
    示例：'同步所有测试运行数据到向量库'
    """
    payload = {"tenant_id": tenant_id, "incremental": incremental}
    if table_name:
        payload["table_name"] = table_name

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{AUTOPILOT_BASE_URL}/sync",
            json=payload,
        )
        result = resp.json()

    if result.get("errors"):
        return f"同步完成，但有错误: {result.get('errors')}"
    return result.get("message", "同步完成。")


@function_tool
async def semantic_search_runs(
    query: str,
    tenant_id: str = "tenant_a",
    scenario_type: str | None = None,
    weather: str | None = None,
    n_results: int = 10,
) -> str:
    """
    【语义搜索测试】用语义搜索查找相关的测试记录。
    可附加结构化过滤条件（场景、天气等）。
    示例：'找出感知表现最差的几次测试'
    """
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
                "n_results": n_results,
            },
        )
        result = resp.json()

    if result.get("success"):
        docs = result.get("results", [])
        if not docs:
            return "未找到匹配的测试结果。"

        output = [f"找到 {len(docs)} 条相关记录:\n"]
        for i, doc in enumerate(docs):
            meta = doc.get("metadata", {})
            table = meta.get("table", "unknown")
            run_id = meta.get("run_id", "")
            output.append(f"{i+1}. [{table}] {run_id}")
            for k, v in meta.items():
                if k not in ("table", "run_id", "tenant_id", "_synced_at"):
                    output.append(f"   - {k}: {v}")
        return "\n".join(output)
    return f"语义搜索失败: {result.get('error', '未知错误')}"


# 导出所有工具
AUTOPILOT_TOOLS = [
    query_autopilot_data,
    analyze_driving_logs,
    get_safety_statistics,
    generate_evaluation_report,
    sync_data_to_vector,
    semantic_search_runs,
]
