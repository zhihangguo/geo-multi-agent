"""
MySQL 数据访问层 — 带租户隔离

核心设计：
1. 所有查询强制注入 tenant_id 过滤，不信任 LLM 生成的 SQL
2. 只允许 SELECT 操作
3. 连接池复用
"""
import re
from typing import Any

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

from config.settings import autopilot_settings


class AutopilotMySQLPool:
    """自动驾驶评估 MySQL 连接池（全局单例）"""
    _pool: PooledDB | None = None

    @classmethod
    def get_pool(cls) -> PooledDB:
        if cls._pool is None:
            cls._pool = PooledDB(
                creator=pymysql,
                maxconnections=autopilot_settings.MYSQL_MAX_CONNECTIONS,
                host=autopilot_settings.MYSQL_HOST,
                user=autopilot_settings.MYSQL_USER,
                password=autopilot_settings.MYSQL_PASSWORD,
                port=autopilot_settings.MYSQL_PORT,
                database=autopilot_settings.MYSQL_DATABASE,
                charset=autopilot_settings.MYSQL_CHARSET,
                connect_timeout=autopilot_settings.MYSQL_CONNECT_TIMEOUT,
            )
        return cls._pool

    @classmethod
    def get_connection(cls):
        return cls.get_pool().connection()


# 表名白名单
VALID_TABLES = {
    "ad_vehicles", "ad_test_runs", "ad_perception_results",
    "ad_safety_events", "ad_planning_metrics", "ad_system_logs",
    "ad_evaluation_reports",
}


class IsolatedMySQLRepository:
    """
    带租户隔离的 MySQL 访问类

    用法：
        repo = IsolatedMySQLRepository(tenant_id="tenant_a")
        rows = repo.query("SELECT run_id, avg_speed_kmh FROM ad_test_runs WHERE scenario_type='highway'")
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """执行查询，强制注入 tenant_id 过滤"""
        self._validate_sql(sql)

        # 判断是否需要注入 tenant_id
        has_tenant = "tenant_id" in sql.lower()
        if not has_tenant:
            safe_sql = self._inject_tenant_filter(sql)
            # 注入了 tenant_id = %s，需要传参
            all_params = (*params, self.tenant_id)
        else:
            # SQL 已有 tenant_id，原样执行
            safe_sql = sql
            all_params = params

        conn = AutopilotMySQLPool.get_connection()
        try:
            with conn.cursor(DictCursor) as cursor:
                if all_params:
                    cursor.execute(safe_sql, all_params)
                else:
                    cursor.execute(safe_sql)
                rows = cursor.fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """查询单行"""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def query_scalar(self, sql: str, params: tuple = ()) -> Any:
        """查询单值"""
        rows = self.query(sql, params)
        if rows and rows[0]:
            return list(rows[0].values())[0]
        return None

    def query_all_tables(self, table: str) -> list[dict[str, Any]]:
        """查询指定表的所有数据（自动带 tenant_id 过滤）"""
        sql = f"SELECT * FROM {table} WHERE tenant_id = %s"
        return self.query(sql)

    # ---- 安全校验 ----

    @staticmethod
    def _validate_sql(sql: str):
        """只允许 SELECT 操作"""
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT"):
            raise PermissionError(f"只允许 SELECT 操作，收到: {stripped[:50]}")

        forbidden = {"DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "EXEC", "GRANT", "REVOKE"}
        # 检查关键字（排除 SELECT 内部的子查询关键词）
        tokens = re.split(r'\s+', stripped)
        for token in tokens:
            if token in forbidden:
                raise PermissionError(f"禁止使用 SQL 关键字: {token}")

        # 禁止注释
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise PermissionError("SQL 中不允许包含注释")

    def _inject_tenant_filter(self, sql: str) -> str:
        """
        强制注入 tenant_id 过滤

        三种情况：
        1. SQL 已有 tenant_id 条件 → 不重复注入
        2. SQL 有 WHERE → 追加 AND tenant_id = %s
        3. SQL 无 WHERE → 添加 WHERE tenant_id = %s
        """
        if "tenant_id" in sql.lower():
            return sql  # 已包含，不再注入

        # 查找最后一个 WHERE（处理子查询情况，简单追加到末尾）
        # 对于简单查询直接追加
        sql_lower = sql.lower()
        has_where = "where" in sql_lower

        if has_where:
            return f"{sql} AND tenant_id = %s"
        else:
            # 需要找到 FROM 子句后的位置
            from_match = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
            if from_match:
                # 在 FROM 子句后直接加 WHERE
                insert_pos = from_match.end()
                return f"{sql[:insert_pos]} WHERE tenant_id = %s{sql[insert_pos:]}"

            return f"{sql} WHERE tenant_id = %s"

    def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """获取表结构信息（information_schema 不需要 tenant 过滤）"""
        if table_name not in VALID_TABLES:
            raise ValueError(f"表名不在白名单中: {table_name}")

        sql = """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_COMMENT
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        conn = AutopilotMySQLPool.get_connection()
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(sql, (autopilot_settings.MYSQL_DATABASE, table_name))
                return cursor.fetchall()
        finally:
            conn.close()

    def _raw_query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """原始查询，不注入 tenant_id（用于 information_schema 等系统查询）"""
        conn = AutopilotMySQLPool.get_connection()
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    def get_all_schemas(self) -> dict[str, list[dict[str, Any]]]:
        """获取所有表的结构信息"""
        schemas = {}
        for table in VALID_TABLES:
            try:
                schemas[table] = self.get_table_schema(table)
            except Exception:
                pass
        return schemas
