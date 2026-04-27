"""
LangGraph Agent 创建模块

使用 create_react_agent 创建带 system prompt 的 ReAct 智能体。
模块级单例避免每次请求重建。
"""
from langgraph.prebuilt import create_react_agent

from .models import build_sub_model
from .tools import TECHNICAL_TOOLS, SERVICE_TOOLS, AUTOPILOT_TOOLS
from .prompts import load_technical_prompt, load_service_prompt, load_autopilot_prompt

# ---------------------------------------------------------------------------
# 模块级缓存：避免每次请求重建 agent
# ---------------------------------------------------------------------------
_technical_agent = None
_service_agent = None
_autopilot_agent = None


def get_technical_agent():
    """获取或创建地质知识专家 Agent (单例)。"""
    global _technical_agent
    if _technical_agent is None:
        model = build_sub_model()
        _technical_agent = create_react_agent(
            model,
            tools=TECHNICAL_TOOLS,
            prompt=load_technical_prompt(),
        )
    return _technical_agent


def get_service_agent():
    """获取或创建野外后勤导航专家 Agent (单例)。"""
    global _service_agent
    if _service_agent is None:
        model = build_sub_model()
        _service_agent = create_react_agent(
            model,
            tools=SERVICE_TOOLS,
            prompt=load_service_prompt(),
        )
    return _service_agent


def get_autopilot_agent():
    """获取或创建自动驾驶评估专家 Agent (单例)。"""
    global _autopilot_agent
    if _autopilot_agent is None:
        model = build_sub_model()
        _autopilot_agent = create_react_agent(
            model,
            tools=AUTOPILOT_TOOLS,
            prompt=load_autopilot_prompt(),
        )
    return _autopilot_agent
