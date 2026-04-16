"""
LangGraph 路由/任务规划模块

支持多任务拆解：LLM 识别用户请求中的多个子任务，
返回任务列表而非单一路由，与 OpenAI Agents SDK 的 Orchestrator 行为对齐。
"""
from typing import Literal, List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from .models import build_main_model

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class TaskItem(BaseModel):
    """单个任务描述"""
    type: Literal["technical", "service"] = Field(
        ..., description="任务类型: technical（地质知识/资讯）或 service（后勤导航）"
    )
    query: str = Field(
        ..., description="传给对应专家的具体查询内容"
    )


class TaskPlan(BaseModel):
    """任务规划结果：包含一个或多个有序任务"""
    tasks: List[TaskItem] = Field(
        ..., description="按执行顺序排列的任务列表"
    )


# ---------------------------------------------------------------------------
# 关键词兜底路由（单任务快速路径）
# ---------------------------------------------------------------------------

TECHNICAL_KEYWORDS = [
    "地质", "勘探", "矿", "岩", "地层", "矿物", "断层", "地震",
    "天气", "预警", "科研", "政策", "成果", "新闻", "今天", "几号", "几点",
    "鉴定", "取样", "地形", "沉积", "构造", "火山",
]

SERVICE_KEYWORDS = [
    "导航", "怎么去", "附近", "补给", "医疗", "村", "驻地", "营地",
    "路线", "位置", "撤离", "最近的", "怎么走",
]


def _keyword_route(user_query: str) -> str | None:
    """基于关键词的兜底路由（仅对明确的单任务有效）。"""
    has_tech = any(k in user_query for k in TECHNICAL_KEYWORDS)
    has_svc = any(k in user_query for k in SERVICE_KEYWORDS)

    # 同时命中两类关键词 → 可能是多任务，交给 LLM
    if has_tech and has_svc:
        return None

    if has_tech:
        return "technical"
    if has_svc:
        return "service"
    return None


# ---------------------------------------------------------------------------
# LLM 任务规划链
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """你是 GeoAssist 的任务规划器。

你的唯一职责是分析用户的请求，把它拆解成一个或多个有序任务。

## 任务类型

1. **technical** — 地质知识、岩石鉴定、矿物识别、地层分析、实时资讯（天气、地震、新闻）等
2. **service** — 查询附近站点（补给/医疗/村庄）、路线导航、位置查询等

## 规则

- 只识别用户**明确提到**的任务，不要推测额外任务
- 如果用户只有一个任务，就只返回一个
- 如果用户有多个任务，按用户描述的顺序排列
- query 字段应保留用户的原始表述，不要改写

## 示例

用户: "查一下今天天气，然后帮我找最近的补给点"
→ tasks: [{"type": "technical", "query": "今天天气怎么样"}, {"type": "service", "query": "帮我找最近的补给点"}]

用户: "这块岩石怎么鉴定？"
→ tasks: [{"type": "technical", "query": "这块岩石怎么鉴定？"}]

用户: "帮我导航到最近的医疗站"
→ tasks: [{"type": "service", "query": "帮我导航到最近的医疗站"}]
"""


def build_planner_chain():
    """构建任务规划链，返回 TaskPlan。"""
    model = build_main_model()
    structured_model = model.with_structured_output(TaskPlan)

    async def plan_tasks(user_query: str) -> TaskPlan:
        # 快速路径：单一关键词匹配
        fallback = _keyword_route(user_query)
        if fallback:
            return TaskPlan(tasks=[TaskItem(type=fallback, query=user_query)])

        # LLM 规划
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=user_query),
        ]
        return await structured_model.ainvoke(messages)

    return plan_tasks
