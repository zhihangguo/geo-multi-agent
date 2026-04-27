"""
数据分析服务 — 日志分析 + 感知分析 + 报告生成
"""
import json
from openai import AsyncOpenAI

from config.settings import autopilot_settings
from repositories.mysql_repository import IsolatedMySQLRepository


class DataAnalysisService:
    """数据分析服务"""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.repo = IsolatedMySQLRepository(tenant_id)

    async def analyze_logs(self, run_id: str) -> str:
        """
        分析指定测试任务的系统日志
        返回：模块分布、级别统计、性能瓶颈识别
        """
        # 查询该 run 的所有日志
        logs = self.repo.query(
            "SELECT module, log_level, message, latency_ms, cpu_usage, memory_mb "
            "FROM ad_system_logs WHERE run_id = %s AND tenant_id = %s "
            "ORDER BY log_time",
            (run_id,),
        )

        if not logs:
            return f"未找到测试任务 {run_id} 的系统日志。"

        # 统计分析
        module_counts = {}
        level_counts = {}
        errors = []
        max_latency = 0
        max_latency_module = ""

        for log in logs:
            mod = log.get("module", "unknown")
            lvl = log.get("log_level", "unknown")
            module_counts[mod] = module_counts.get(mod, 0) + 1
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

            latency = log.get("latency_ms")
            if latency and latency > max_latency:
                max_latency = latency
                max_latency_module = mod

            if lvl in ("ERROR", "CRITICAL"):
                errors.append(log)

        # 生成分析报告
        report_lines = [f"## 测试任务 {run_id} 日志分析报告\n"]
        report_lines.append(f"**总日志条数**: {len(logs)}\n")

        report_lines.append("### 模块分布")
        for mod, count in sorted(module_counts.items(), key=lambda x: -x[1]):
            report_lines.append(f"- {mod}: {count} 条")

        report_lines.append("\n### 级别分布")
        for lvl, count in sorted(level_counts.items(), key=lambda x: -x[1]):
            report_lines.append(f"- {lvl}: {count} 条")

        report_lines.append(f"\n### 性能瓶颈")
        report_lines.append(f"- 最高延迟: {max_latency}ms ({max_latency_module} 模块)")

        if errors:
            report_lines.append(f"\n### 错误/严重日志 ({len(errors)} 条)")
            for err in errors:
                report_lines.append(f"- [{err['log_level']}] {err['module']}: {str(err['message'])[:100]}")
        else:
            report_lines.append("\n### 无错误或严重级别日志")

        return "\n".join(report_lines)

    async def get_safety_statistics(self, filters: dict | None = None) -> str:
        """
        获取安全事件统计
        支持按时间范围、车辆、场景类型、严重程度过滤
        """
        conditions = ["e.tenant_id = %s"]
        params: list = [self.tenant_id]

        if filters:
            if filters.get("vehicle_id"):
                conditions.append("t.vehicle_id = %s")
                params.append(filters["vehicle_id"])
            if filters.get("scenario_type"):
                conditions.append("t.scenario_type = %s")
                params.append(filters["scenario_type"])
            if filters.get("severity"):
                conditions.append("e.severity = %s")
                params.append(filters["severity"])
            if filters.get("event_type"):
                conditions.append("e.event_type = %s")
                params.append(filters["event_type"])

        where_clause = " AND ".join(conditions)

        # 按类型和严重级别统计
        stats = self.repo.query(
            f"SELECT e.event_type, e.severity, COUNT(*) as count, "
            f"AVG(e.ego_speed_kmh) as avg_speed, "
            f"SUM(CASE WHEN e.human_intervention THEN 1 ELSE 0 END) as interventions "
            f"FROM ad_safety_events e "
            f"JOIN ad_test_runs t ON e.run_id = t.run_id "
            f"WHERE {where_clause} "
            f"GROUP BY e.event_type, e.severity "
            f"ORDER BY count DESC",
            tuple(params),
        )

        if not stats:
            return "未找到匹配的安全事件数据。"

        lines = ["## 安全事件统计\n"]
        total_events = sum(s["count"] for s in stats)
        total_interventions = sum(s["interventions"] or 0 for s in stats)
        lines.append(f"**总事件数**: {total_events}")
        lines.append(f"**人工接管次数**: {total_interventions}\n")

        lines.append("### 按类型和严重级别")
        for s in stats:
            sev_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(s["severity"], "")
            lines.append(
                f"- {sev_icon} {s['event_type']} ({s['severity']}): "
                f"{s['count']} 次, 平均速度 {s['avg_speed'] or 0:.1f}km/h"
            )

        return "\n".join(lines)

    async def generate_report_summary(self, run_id: str) -> str:
        """
        生成指定测试任务的评估报告摘要
        """
        report = self.repo.query_one(
            "SELECT r.*, t.vehicle_id, t.scenario_type, t.weather, t.location, "
            "t.test_engineer, v.model_name "
            "FROM ad_evaluation_reports r "
            "JOIN ad_test_runs t ON r.run_id = t.run_id "
            "LEFT JOIN ad_vehicles v ON t.vehicle_id = v.vehicle_id "
            "WHERE r.run_id = %s AND r.tenant_id = %s",
            (run_id,),
        )

        if not report:
            return f"未找到测试任务 {run_id} 的评估报告。"

        lines = [f"## 评估报告: {run_id}\n"]
        lines.append(f"**车辆**: {report.get('model_name', report.get('vehicle_id', ''))}")
        lines.append(f"**场景**: {report.get('scenario_type', '')}")
        lines.append(f"**天气**: {report.get('weather', '')}")
        lines.append(f"**地点**: {report.get('location', '')}")
        lines.append(f"**测试工程师**: {report.get('test_engineer', '')}\n")

        lines.append("### 综合评分")
        lines.append(f"- **总分**: {report.get('overall_score', 0):.1f} / 100")
        lines.append(f"- 感知: {report.get('perception_score', 0):.1f}")
        lines.append(f"- 规划: {report.get('planning_score', 0):.1f}")
        lines.append(f"- 安全: {report.get('safety_score', 0):.1f}")
        lines.append(f"- 舒适度: {report.get('comfort_score', 0):.1f}")
        lines.append(f"- 效率: {report.get('efficiency_score', 0):.1f}\n")

        lines.append(f"**总里程**: {report.get('total_distance_km', 0):.1f} km")
        lines.append(f"**总时长**: {report.get('total_duration_min', 0):.1f} 分钟")
        lines.append(f"**人工接管**: {report.get('intervention_count', 0)} 次")
        lines.append(f"**严重事件**: {report.get('critical_event_count', 0)} 次\n")

        summary = report.get("summary", "")
        if summary:
            lines.append(f"**分析摘要**:\n{summary}\n")

        recs = report.get("recommendations", "")
        if recs:
            lines.append(f"**改进建议**:\n{recs}")

        return "\n".join(lines)
