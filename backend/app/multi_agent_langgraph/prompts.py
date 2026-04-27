from infrastructure.ai.prompt_loader import load_prompt


def load_orchestrator_prompt() -> str:
    return load_prompt("orchestrator_v1")


def load_technical_prompt() -> str:
    return load_prompt("technical_agent")


def load_service_prompt() -> str:
    return load_prompt("comprehensive_service_agent")


def load_autopilot_prompt() -> str:
    return load_prompt("autopilot_agent")
