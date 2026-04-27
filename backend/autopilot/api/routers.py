"""
自动驾驶评估服务 API 路由

端点：
- POST /autopilot/query       — 自然语言查询（Text2SQL + 向量搜索）
- POST /autopilot/analyze     — 日志/感知数据分析
- POST /autopilot/report      — 生成评估报告摘要
- POST /autopilot/stats       — 安全事件统计
- POST /autopilot/sync        — MySQL → 向量库同步
- POST /autopilot/semantic    — 向量语义搜索
- GET  /autopilot/schema      — 获取数据库表结构
- GET  /autopilot/health      — 健康检查
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from services.security_service import SecurityService
from services.text2sql_service import text2sql, generate_natural_answer
from services.data_analysis_service import DataAnalysisService
from services.mysql2vector_service import sync_table_to_vector, sync_all_tables
from repositories.vector_repository import AutopilotVectorRepository
from repositories.mysql_repository import IsolatedMySQLRepository

router = APIRouter(prefix="/autopilot", tags=["自动驾驶评估"])


# ===== 请求模型 =====
class AutopilotQueryRequest(BaseModel):
    question: str = Field(..., description="自然语言查询问题")
    tenant_id: str = Field(..., description="租户ID")
    search_mode: str = Field(default="auto", description="auto/text2sql/vector")
    where_filters: Optional[dict] = Field(default=None, description="结构化过滤条件(向量搜索用)")


class AutopilotAnalyzeRequest(BaseModel):
    run_id: str = Field(..., description="测试任务ID")
    tenant_id: str = Field(..., description="租户ID")
    analysis_type: str = Field(default="logs", description="logs/safety/report")
    filters: Optional[dict] = Field(default=None)


class AutopilotReportRequest(BaseModel):
    run_id: str = Field(..., description="测试任务ID")
    tenant_id: str = Field(..., description="租户ID")


class AutopilotSyncRequest(BaseModel):
    tenant_id: str = Field(..., description="租户ID")
    table_name: Optional[str] = Field(default=None, description="指定表名, None=全部表")
    incremental: bool = Field(default=False, description="是否增量同步")


class AutopilotSemanticRequest(BaseModel):
    query: str = Field(..., description="语义搜索关键词")
    tenant_id: str = Field(..., description="租户ID")
    where_filters: Optional[dict] = Field(default=None)
    n_results: int = Field(default=10, ge=1, le=50)


# ===== 端点 =====
@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "autopilot-eval"}


@router.get("/schema")
async def get_schema(tenant_id: str = "default"):
    """获取数据库表结构"""
    repo = IsolatedMySQLRepository(tenant_id)
    schemas = repo.get_all_schemas()
    return {"success": True, "schemas": schemas}


@router.post("/query")
async def query_autopilot_data(req: AutopilotQueryRequest):
    """自然语言查询自动驾驶数据库"""
    # 安全校验
    security = SecurityService(req.tenant_id)
    try:
        req.question = security.sanitize_input(req.question)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    mode = req.search_mode.lower()

    if mode == "vector":
        # 纯向量搜索
        vector_repo = AutopilotVectorRepository(req.tenant_id)
        results = vector_repo.semantic_search(
            query=req.question,
            where_filter=req.where_filters,
            n_results=10,
        )
        docs = []
        if results.get("documents"):
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                docs.append({"document": doc, "metadata": meta})
        return {"success": True, "mode": "vector", "results": docs, "total": len(docs)}

    # Text2SQL (auto 模式也默认用这个)
    result = await text2sql(req.question, req.tenant_id)

    if result["success"]:
        # 生成自然语言回答
        try:
            answer = await generate_natural_answer(req.question, result["data"], result["sql"])
        except Exception:
            answer = None

        return {
            "success": True,
            "mode": "text2sql",
            "sql": result["sql"],
            "data": result["data"],
            "row_count": result["row_count"],
            "answer": answer,
            "from_cache": result.get("from_cache", False),
        }

    return {"success": False, "error": result.get("error", "未知错误"), "sql": result.get("sql", "")}


@router.post("/analyze")
async def analyze_data(req: AutopilotAnalyzeRequest):
    """日志/感知数据分析"""
    security = SecurityService(req.tenant_id)
    try:
        security.sanitize_input(f"analyze {req.run_id}")
    except ValueError as e:
        return {"success": False, "error": str(e)}

    service = DataAnalysisService(req.tenant_id)

    if req.analysis_type == "logs":
        result = await service.analyze_logs(req.run_id)
        return {"success": True, "analysis_type": "logs", "content": result}
    elif req.analysis_type == "safety":
        result = await service.get_safety_statistics(req.filters)
        return {"success": True, "analysis_type": "safety", "content": result}
    elif req.analysis_type == "report":
        result = await service.generate_report_summary(req.run_id)
        return {"success": True, "analysis_type": "report", "content": result}

    return {"success": False, "error": "不支持的分析类型"}


@router.post("/report")
async def generate_report(req: AutopilotReportRequest):
    """生成评估报告摘要"""
    security = SecurityService(req.tenant_id)
    try:
        security.sanitize_input(f"report {req.run_id}")
    except ValueError as e:
        return {"success": False, "error": str(e)}

    service = DataAnalysisService(req.tenant_id)
    result = await service.generate_report_summary(req.run_id)
    return {"success": True, "content": result}


@router.post("/stats")
async def get_safety_stats(req: AutopilotAnalyzeRequest):
    """安全事件统计"""
    security = SecurityService(req.tenant_id)
    try:
        security.sanitize_input("safety stats")
    except ValueError as e:
        return {"success": False, "error": str(e)}

    service = DataAnalysisService(req.tenant_id)
    result = await service.get_safety_statistics(req.filters)
    return {"success": True, "content": result}


@router.post("/sync")
async def sync_data(req: AutopilotSyncRequest):
    """MySQL → 向量库同步"""
    if req.table_name:
        result = sync_table_to_vector(req.table_name, req.tenant_id, req.incremental)
    else:
        result = sync_all_tables(req.tenant_id)

    status_code = 200 if not result.get("errors") else 207
    return result


@router.post("/semantic")
async def semantic_search(req: AutopilotSemanticRequest):
    """向量语义搜索"""
    security = SecurityService(req.tenant_id)
    try:
        req.query = security.sanitize_input(req.query)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # 过滤掉 None 值的过滤条件
    where_filter = None
    if req.where_filters:
        where_filter = {k: v for k, v in req.where_filters.items() if v is not None and v != "None"}
        if not where_filter:
            where_filter = None

    vector_repo = AutopilotVectorRepository(req.tenant_id)
    results = vector_repo.semantic_search(
        query=req.query,
        where_filter=where_filter,
        n_results=req.n_results,
    )

    docs = []
    if results.get("documents"):
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results.get("distances", [[]])[0] if results.get("distances") else [None] * len(results["documents"][0]),
        ):
            docs.append({
                "document": doc,
                "metadata": {k: v for k, v in meta.items() if k != "tenant_id"},
                "distance": dist,
            })

    return {"success": True, "results": docs, "total": len(docs)}
