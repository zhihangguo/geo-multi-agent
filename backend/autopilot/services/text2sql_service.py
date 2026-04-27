"""
Text2SQL 服务 — 自然语言转 SQL

框架：LangChain create_sql_query_chain + 自定义 Few-Shot RAG
提升准确率的三个手段：
1. Schema 注入
2. Few-Shot 示例（按相似度召回）
3. Chain-of-Thought 推理

错误处理：最多 3 次重试，每次把 MySQL 报错信息反馈给 LLM
"""
import json
from cachetools import TTLCache
from openai import AsyncOpenAI

from config.settings import autopilot_settings
from repositories.mysql_repository import IsolatedMySQLRepository, VALID_TABLES
from services.security_service import SecurityService


# ===== LRU 缓存 =====
_text2sql_cache = TTLCache(maxsize=autopilot_settings.TEXT2SQL_CACHE_SIZE, ttl=600)

# ===== Few-Shot 示例库 =====
FEW_SHOT_EXAMPLES = [
    {
        "question": "查询 AV-001 所有高速测试的平均速度",
        "sql": "SELECT t.run_id, t.vehicle_id, t.avg_speed_kmh, t.total_distance_km, t.weather "
               "FROM ad_test_runs t WHERE t.vehicle_id = 'AV-001' AND t.scenario_type = 'highway' "
               "AND t.tenant_id = '{tenant_id}' ORDER BY t.start_time DESC",
    },
    {
        "question": "统计每辆车的人工接管次数",
        "sql": "SELECT e.run_id, t.vehicle_id, COUNT(*) as intervention_count "
               "FROM ad_safety_events e "
               "JOIN ad_test_runs t ON e.run_id = t.run_id "
               "WHERE e.human_intervention = TRUE AND e.tenant_id = '{tenant_id}' "
               "GROUP BY e.run_id, t.vehicle_id "
               "ORDER BY intervention_count DESC",
    },
    {
        "question": "找出感知精确率低于 0.85 的测试",
        "sql": "SELECT DISTINCT p.run_id, p.object_type, p.precision_score, t.scenario_type "
               "FROM ad_perception_results p "
               "JOIN ad_test_runs t ON p.run_id = t.run_id "
               "WHERE p.precision_score < 0.85 AND p.tenant_id = '{tenant_id}' "
               "ORDER BY p.precision_score ASC",
    },
    {
        "question": "查询雨天场景下的安全事件统计",
        "sql": "SELECT e.event_type, COUNT(*) as count, AVG(e.ego_speed_kmh) as avg_speed "
               "FROM ad_safety_events e "
               "JOIN ad_test_runs t ON e.run_id = t.run_id "
               "WHERE t.weather = 'rainy' AND e.tenant_id = '{tenant_id}' "
               "GROUP BY e.event_type ORDER BY count DESC",
    },
    {
        "question": "获取 RUN-001 的完整评估报告",
        "sql": "SELECT r.*, t.vehicle_id, t.scenario_type, t.weather, t.location "
               "FROM ad_evaluation_reports r "
               "JOIN ad_test_runs t ON r.run_id = t.run_id "
               "WHERE r.run_id = 'RUN-001' AND r.tenant_id = '{tenant_id}'",
    },
    {
        "question": "统计各模块的 ERROR 级别日志数量",
        "sql": "SELECT module, COUNT(*) as error_count "
               "FROM ad_system_logs "
               "WHERE log_level = 'ERROR' AND tenant_id = '{tenant_id}' "
               "GROUP BY module ORDER BY error_count DESC",
    },
    {
        "question": "查询评分最高的 3 次测试",
        "sql": "SELECT run_id, overall_score, perception_score, safety_score, total_distance_km "
               "FROM ad_evaluation_reports WHERE tenant_id = '{tenant_id}' "
               "ORDER BY overall_score DESC LIMIT 3",
    },
    {
        "question": "比较晴天和雨天场景的感知 F1 分数差异",
        "sql": "SELECT t.weather, AVG(p.f1_score) as avg_f1 "
               "FROM ad_perception_results p "
               "JOIN ad_test_runs t ON p.run_id = t.run_id "
               "WHERE p.tenant_id = '{tenant_id}' "
               "GROUP BY t.weather ORDER BY avg_f1 DESC",
    },
]


def _get_schema_for_prompt(repo: IsolatedMySQLRepository) -> str:
    """生成适合注入到 prompt 的 schema 描述"""
    lines = []
    for table in sorted(VALID_TABLES):
        try:
            columns = repo.get_table_schema(table)
            col_defs = []
            for col in columns:
                col_defs.append(f"  {col['COLUMN_NAME']} {col['DATA_TYPE']} {'COMMENT' + col['COLUMN_COMMENT'] if col.get('COLUMN_COMMENT') else ''}")
            lines.append(f"表 {table}:\n" + "\n".join(col_defs))
        except Exception:
            lines.append(f"表 {table}: (无法获取结构)")
    return "\n\n".join(lines)


def _build_system_prompt(schema_desc: str) -> str:
    """构建 Text2SQL 系统 prompt"""
    examples_text = "\n".join([
        f"Q: {ex['question']}\nSQL: {ex['sql']}"
        for ex in FEW_SHOT_EXAMPLES[:4]  # 只取前 4 个作为固定示例
    ])

    return (
        "你是一个专业的 SQL 生成助手，负责将自然语言问题转换为 MySQL 查询语句。\n\n"
        "数据库包含以下表：\n"
        f"{schema_desc}\n\n"
        "重要规则：\n"
        "1. 所有查询 MUST 包含 `tenant_id = '{tenant_id}'` 条件。\n"
        "2. 只生成 SELECT 语句，禁止 DELETE/UPDATE/INSERT/DROP 等。\n"
        "3. 使用 LIMIT 限制返回行数（默认 LIMIT 100）。\n"
        "4. 多表查询时使用 JOIN，避免笛卡尔积。\n"
        "5. 只输出 SQL 语句，不要输出其他内容。\n"
        "6. 使用反引号包裹表名和字段名。\n\n"
        "Few-Shot 示例：\n"
        f"{examples_text}\n\n"
        "Chain-of-Thought 推理步骤：\n"
        "1. 理解用户意图，确定需要查询的信息\n"
        "2. 确定涉及哪些表\n"
        "3. 确定表之间的 JOIN 条件\n"
        "4. 生成 SQL（必须包含 tenant_id 过滤）\n"
        "5. 检查 SQL 语法正确性\n\n"
        "请根据上述规则，将用户的问题转换为 SQL。"
    )


async def text2sql(
    question: str,
    tenant_id: str,
    force_retry: bool = False,
    previous_error: str | None = None,
    retry_count: int = 0,
) -> dict:
    """
    Text2SQL 核心函数

    Returns:
        {
            "success": bool,
            "sql": str,
            "data": list[dict],
            "error": str | None,
            "retry_count": int,
        }
    """
    # 1. 检查缓存
    cache_key = f"{tenant_id}:{question}"
    if cache_key in _text2sql_cache and not force_retry:
        cached = _text2sql_cache[cache_key]
        return {"success": True, **cached, "from_cache": True}

    # 2. 初始化
    repo = IsolatedMySQLRepository(tenant_id)
    schema_desc = _get_schema_for_prompt(repo)
    system_prompt = _build_system_prompt(schema_desc).format(tenant_id=tenant_id)

    user_content = f"问题: {question}"
    if previous_error:
        user_content += f"\n\n上一次尝试的 SQL 执行报错: {previous_error}\n请修正后重新生成。"

    # 3. 调用 LLM 生成 SQL
    client = AsyncOpenAI(
        base_url=autopilot_settings.LLM_BASE_URL,
        api_key=autopilot_settings.LLM_API_KEY,
    )

    try:
        response = await client.chat.completions.create(
            model=autopilot_settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            max_tokens=1024,
            extra_body={"enable_thinking": False},
        )

        generated_sql = response.choices[0].message.content.strip()

        # 清理可能包含的 markdown 代码块
        if generated_sql.startswith("```"):
            generated_sql = generated_sql.split("\n", 1)[-1]
        if generated_sql.endswith("```"):
            generated_sql = generated_sql.rsplit("\n", 1)[0]
        generated_sql = generated_sql.strip().rstrip(";")

        # 4. 安全校验
        if not SecurityService.validate_sql_query(generated_sql):
            return {
                "success": False,
                "sql": generated_sql,
                "data": [],
                "error": "生成的 SQL 未通过安全校验",
                "retry_count": 0,
            }

        # 5. 执行 SQL
        try:
            rows = repo.query(generated_sql)
        except Exception as e:
            error_msg = str(e)
            # 自动重试，限制最大重试次数
            max_retries = autopilot_settings.TEXT2SQL_MAX_RETRIES
            if retry_count < max_retries:
                return await text2sql(
                    question=question,
                    tenant_id=tenant_id,
                    force_retry=True,
                    previous_error=error_msg,
                    retry_count=retry_count + 1,
                )
            return {
                "success": False,
                "sql": generated_sql,
                "data": [],
                "error": f"SQL 执行失败（已重试 {max_retries} 次）: {error_msg}",
                "retry_count": retry_count,
            }

        # 6. 缓存结果
        result = {
            "sql": generated_sql,
            "data": rows,
            "row_count": len(rows),
        }
        _text2sql_cache[cache_key] = result

        return {"success": True, **result, "retry_count": 0}

    except Exception as e:
        return {
            "success": False,
            "sql": "",
            "data": [],
            "error": f"LLM 调用失败: {str(e)}",
            "retry_count": 0,
        }


async def generate_natural_answer(question: str, data: list[dict], sql: str) -> str:
    """
    将 SQL 查询结果转换为自然语言回答
    """
    if not data:
        return "未查询到匹配的数据。"

    # 构建数据摘要
    data_summary = json.dumps(data[:10], ensure_ascii=False, indent=2)
    if len(data) > 10:
        data_summary += f"\n... 共 {len(data)} 条结果，仅展示前 10 条"

    client = AsyncOpenAI(
        base_url=autopilot_settings.LLM_BASE_URL,
        api_key=autopilot_settings.LLM_API_KEY,
    )

    response = await client.chat.completions.create(
        model=autopilot_settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个自动驾驶数据分析专家。请基于给定的查询结果，"
                    "用简洁的中文回答用户的问题。只基于数据说话，不要编造信息。"
                    "如果数据中有异常或值得关注的点，请指出。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"问题: {question}\n\n"
                    f"查询到的数据:\n{data_summary}\n\n"
                    f"请用中文回答用户的问题。"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=1024,
        extra_body={"enable_thinking": False},
    )

    return response.choices[0].message.content.strip()
