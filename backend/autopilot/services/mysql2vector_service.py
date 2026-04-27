"""
MySQL → 向量库同步服务

将 MySQL 表中的数据转换为自然语言描述 + metadata 后存入 ChromaDB。
支持全量同步和增量同步（只同步新增/更新的行）。
"""
import json
from datetime import datetime

from repositories.mysql_repository import IsolatedMySQLRepository
from repositories.vector_repository import AutopilotVectorRepository


def _row_to_document(table: str, row: dict) -> tuple[str, dict]:
    """将一行 MySQL 数据转为 (自然语言描述, metadata)"""
    tenant_id = row.get("tenant_id", "unknown")

    if table == "ad_test_runs":
        doc_text = (
            f"测试 {row.get('run_id', '')}，车辆 {row.get('vehicle_id', '')}，"
            f"{row.get('start_time', '')} 在 {row.get('location', '')} "
            f"进行 {row.get('scenario_type', '')} 场景测试，"
            f"行驶 {row.get('total_distance_km', 0)}km，"
            f"平均速度 {row.get('avg_speed_kmh', 0)}km/h，"
            f"天气 {row.get('weather', '')}，路面 {row.get('road_condition', '')}，"
            f"状态 {row.get('status', '')}"
        )
        metadata = {
            "table": table,
            "run_id": row.get("run_id", ""),
            "vehicle_id": row.get("vehicle_id", ""),
            "scenario_type": row.get("scenario_type", ""),
            "weather": row.get("weather", ""),
            "road_condition": row.get("road_condition", ""),
            "status": row.get("status", ""),
            "total_distance_km": row.get("total_distance_km", 0),
            "avg_speed_kmh": row.get("avg_speed_kmh", 0),
            "start_time": str(row.get("start_time", "")),
        }
    elif table == "ad_perception_results":
        doc_text = (
            f"测试 {row.get('run_id', '')} 的 {row.get('object_type', '')} 感知评估，"
            f"精确率 {row.get('precision_score', 0):.3f}，"
            f"召回率 {row.get('recall_score', 0):.3f}，"
            f"F1 分数 {row.get('f1_score', 0):.3f}，"
            f"平均 IoU {row.get('avg_iou', 0):.3f}，"
            f"检测延迟 {row.get('detection_latency_ms', 0)}ms"
        )
        metadata = {
            "table": table,
            "run_id": row.get("run_id", ""),
            "object_type": row.get("object_type", ""),
            "precision_score": row.get("precision_score", 0),
            "recall_score": row.get("recall_score", 0),
            "f1_score": row.get("f1_score", 0),
        }
    elif table == "ad_safety_events":
        doc_text = (
            f"测试 {row.get('run_id', '')} 发生 {row.get('event_type', '')} 安全事件，"
            f"严重程度 {row.get('severity', '')}，"
            f"{'人工已接管' if row.get('human_intervention') else '系统自动处理'}，"
            f"事件发生时车速 {row.get('ego_speed_kmh', 0)}km/h"
        )
        metadata = {
            "table": table,
            "run_id": row.get("run_id", ""),
            "event_type": row.get("event_type", ""),
            "severity": row.get("severity", ""),
            "human_intervention": row.get("human_intervention", False),
        }
    elif table == "ad_evaluation_reports":
        doc_text = (
            f"测试 {row.get('run_id', '')} 评估报告，"
            f"综合评分 {row.get('overall_score', 0):.1f}，"
            f"感知 {row.get('perception_score', 0):.1f}，"
            f"安全 {row.get('safety_score', 0):.1f}，"
            f"规划 {row.get('planning_score', 0):.1f}，"
            f"人工接管 {row.get('intervention_count', 0)} 次，"
            f"严重事件 {row.get('critical_event_count', 0)} 次"
        )
        metadata = {
            "table": table,
            "run_id": row.get("run_id", ""),
            "overall_score": row.get("overall_score", 0),
            "perception_score": row.get("perception_score", 0),
            "safety_score": row.get("safety_score", 0),
        }
    elif table == "ad_planning_metrics":
        doc_text = (
            f"测试 {row.get('run_id', '')} 规划指标，"
            f"舒适度 {row.get('comfort_score', 0):.1f}，"
            f"效率 {row.get('efficiency_score', 0):.1f}，"
            f"安全 {row.get('safety_score', 0):.1f}，"
            f"路径偏差 {row.get('path_deviation_m', 0):.2f}m"
        )
        metadata = {
            "table": table,
            "run_id": row.get("run_id", ""),
            "comfort_score": row.get("comfort_score", 0),
            "efficiency_score": row.get("efficiency_score", 0),
            "safety_score": row.get("safety_score", 0),
        }
    elif table == "ad_system_logs":
        doc_text = (
            f"测试 {row.get('run_id', '')} 的 {row.get('module', '')} 模块 "
            f"{row.get('log_level', '')} 日志: {str(row.get('message', ''))[:200]}"
        )
        metadata = {
            "table": table,
            "run_id": row.get("run_id", ""),
            "module": row.get("module", ""),
            "log_level": row.get("log_level", ""),
        }
    else:
        doc_text = json.dumps(row, ensure_ascii=False, default=str)
        metadata = {"table": table, "tenant_id": tenant_id}

    metadata["tenant_id"] = tenant_id
    metadata["_synced_at"] = datetime.now().isoformat()
    return doc_text, metadata


def sync_table_to_vector(
    table_name: str,
    tenant_id: str,
    incremental: bool = False,
) -> dict:
    """
    将 MySQL 指定表同步到向量库

    Args:
        table_name: 表名
        tenant_id: 租户 ID
        incremental: 是否增量同步（默认全量）

    Returns:
        {"synced": int, "skipped": int, "error": str|None}
    """
    mysql_repo = IsolatedMySQLRepository(tenant_id)
    vector_repo = AutopilotVectorRepository(tenant_id)

    if incremental:
        # 增量同步：只同步今天新增的数据
        today = datetime.now().strftime("%Y-%m-%d")
        if table_name == "ad_test_runs":
            rows = mysql_repo.query(
                f"SELECT * FROM {table_name} WHERE tenant_id = %s "
                f"AND DATE(start_time) >= %s",
                (tenant_id, today),
            )
        else:
            rows = mysql_repo.query(
                f"SELECT * FROM {table_name} WHERE tenant_id = %s",
                (tenant_id,),
            )
    else:
        rows = mysql_repo.query_all_tables(table_name)

    if not rows:
        return {"synced": 0, "skipped": 0, "error": None, "message": "无数据需要同步"}

    documents = []
    metadatas = []
    doc_ids = []

    synced_count = 0
    skipped_count = 0

    for row in rows:
        try:
            doc_text, metadata = _row_to_document(table_name, row)
            doc_id = f"{tenant_id}_{table_name}_{row.get('id', row.get('run_id', row.get('event_id', '')))}"

            documents.append(doc_text)
            metadatas.append(metadata)
            doc_ids.append(doc_id)
            synced_count += 1
        except Exception as e:
            skipped_count += 1

    # 批量写入
    if documents:
        vector_repo.add_batch(documents, metadatas, doc_ids)

    return {
        "synced": synced_count,
        "skipped": skipped_count,
        "error": None,
        "message": f"成功同步 {synced_count} 条记录到向量库",
    }


def sync_all_tables(tenant_id: str) -> dict:
    """同步所有表到向量库"""
    tables = [
        "ad_test_runs", "ad_perception_results", "ad_safety_events",
        "ad_planning_metrics", "ad_system_logs", "ad_evaluation_reports",
    ]
    total_synced = 0
    total_skipped = 0
    errors = []

    for table in tables:
        try:
            result = sync_table_to_vector(table, tenant_id)
            total_synced += result["synced"]
            total_skipped += result["skipped"]
        except Exception as e:
            errors.append(f"{table}: {str(e)}")

    return {
        "total_synced": total_synced,
        "total_skipped": total_skipped,
        "errors": errors,
    }
