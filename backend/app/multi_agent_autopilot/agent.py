"""
自动驾驶评估 Agent（OpenAI Agents SDK 版本）
"""
from agents import Agent, ModelSettings
from infrastructure.ai.openai_client import sub_model
from .prompts import AUTOPILOT_AGENT_PROMPT
from .tools import AUTOPILOT_TOOLS

autopilot_agent = Agent(
    name="自动驾驶评估专家",
    instructions=AUTOPILOT_AGENT_PROMPT.strip(),
    model=sub_model,
    model_settings=ModelSettings(
        temperature=0,
        extra_body={"enable_thinking": False},
    ),
    tools=AUTOPILOT_TOOLS,
)
