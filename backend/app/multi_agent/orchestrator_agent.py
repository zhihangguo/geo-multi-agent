import asyncio
from agents import (
    Agent,
    ModelSettings,
    Runner
)
from infrastructure.ai.openai_client import sub_model
from infrastructure.ai.openai_client import main_model
from infrastructure.ai.prompt_loader import load_prompt
from multi_agent.agent_factory import AGENT_TOOLS
from infrastructure.tools.mcp.mcp_servers import search_mcp_client, baidu_mcp_client
from contextlib import AsyncExitStack

# 1. 创建主调度智能体
orchestrator_agent = Agent(
    name="GeoAssist主调度",
    instructions=load_prompt("orchestrator_v1"),
    # model=main_model,   # 推理模型（ds_r1[1.科学 2.计算 3.需求拆解]） (已推理为主，干活其次【funcation_call】)
    model=sub_model,      # 通用模型（已干活为主 推理可能有或者都没有）
    model_settings=ModelSettings(
        temperature=0,
        # 禁用 Qwen3 的深度思考模式，避免所有输出都走 reasoning 通道导致 ANSWER 为空
        extra_body={"enable_thinking": False},
    ),
    # 直接使用Agent Tools
    tools=AGENT_TOOLS,
)


# 3. 测试方法
async def run_single_test(case_name: str, input_text: str):
    print(f"\n{'=' * 80}")
    print(f"测试用例: {case_name}")
    print(f"输入: \"{input_text}\"")
    ("-" * 80)

    # 使用 AsyncExitStack 同时管理多个连接
    async with AsyncExitStack() as stack:
        try:
            print("连接 MCP 服务中...")
            # 1. 进入上下文
            await stack.enter_async_context(search_mcp_client)
            await stack.enter_async_context(baidu_mcp_client)
            print("思考中...")

            # 2. 使用流式处理运行 Orchestrator Agent
            result = Runner.run_streamed(
                starting_agent=orchestrator_agent,
                input=input_text,
            )

            # 3. 遍历流式事件
            async for event in result.stream_events():

                # 3.1 run_item_stream_event级别的事假（Agent运行时产生的事假）
                if event.type == "run_item_stream_event":
                    # a. Agent运行时的工具调用事件
                    if hasattr(event, "name") and event.name == "tool_called":
                        from agents import ToolCallItem
                        if isinstance(event.item, ToolCallItem):
                            raw_item = event.item.raw_item
                            print(f"\n调用工具名:{raw_item.name}--->工具参数:{raw_item.arguments}")

                    # b. Agent运行时的工具执行完后事件
                    elif hasattr(event, 'name') and event.name == "tool_output":
                        from agents import ToolCallOutputItem
                        if isinstance(event.item, ToolCallOutputItem):
                            print(f"调用工具结果:{event.item.output}")

            # 4. 打印最终结果（最后协调Agent的输出）
            print(f"\n最终输出（来自 {result.last_agent.name}）:")
            print(f"{result.final_output}")

        except Exception as e:
            print(f"\n 异常原因 {e}\n")


async def main():
    print("\n" + "=" * 80)
    print("测试协调Agent (Orchestrator)")
    print("=" * 80)

    # 定义地质野外作业测试案例
    test_cases = [
        # A: 咒询地质知识智能体
        # ("\u5355\u4e2a\u4efb\u52a1\uff08\u5b9e\u65f6\u8d44\u8baf\uff09", "\u4eca\u5929\u4f5c\u4e1a\u533a\u9644\u8fd1\u5929\u6c14\u600e\u4e48\u6837\uff1f"),
        # ("\u5355\u4e2a\u4efb\u52a1\uff08\u5730\u8d28\u77e5\u8bc6\uff09", "\u8d64\u8272\u7684\u5ca9\u77f3\u548c\u7070\u8272\u7684\u5ca9\u77f3\u6709\u4ec0\u4e48\u533a\u522b\uff1f"),
        # ("\u7ec4\u5408\u4efb\u52a1\uff081.\u5730\u8d28\u77e5\u8bc6 2.\u5929\u6c14\uff09", "\u82b1\u5c97\u5ca9\u600e\u4e48\u5c0f\u5fc3\u5730\u5c42\uff0c\u9806\u4fbf\u770b\u4e00\u4e0b\u4eca\u5929\u5929\u6c14\u5982\u4f55"),
        # ("\u7ec4\u5408\u4efb\u52a1\uff081.\u5929\u6c14 2.\u5730\u8d28\u77e5\u8bc6\uff09", "\u5148\u770b\u4e00\u4e0b\u4eca\u5929\u5929\u6c14\u600e\u4e48\u6837\uff0c\u987a\u4fbf\u95ee\u4e00\u4e0b\u91ce\u5916\u5982\u4f55\u5224\u65ad\u65ad\u5c42\u9762\u7684\u5c42\u4f4d"),

        # B: 咒询野外后勤导航智能体
        # ("\u5355\u4e2a\u4efb\u52a1\uff08\u540e\u52e4\u7ad9\u70b9\uff09", "\u5e2e\u6211\u627e\u4e2a\u6700\u8fd1\u7684\u8865\u7ed9\u70b9"),
        # ("\u5355\u4e2a\u4efb\u52a1\uff08POI\u5bfc\u822a\uff09", "\u5929\u5b89\u95e8\u5e7f\u573a\u90fd\u6709\u54ea\u4e9b\u5546\u573a"),
        # ("\u7ec4\u5408\u4efb\u52a1\uff081.\u540e\u52e4 2.POI\uff09", "\u4e16\u754c\u5730\u8d28\u516c\u56ed\u600e\u4e48\u53bb\uff1f\uff0c\u987a\u4fbf\u770b\u4e00\u4e0b\u5b83\u9644\u8fd1\u90fd\u6709\u54ea\u4e9b\u5751\u70b9"),

        # ("\u591a\u8df3\u4efb\u52a1(\u5148\u5b9e\u65f6\u5929\u6c14\u518d\u540e\u52e4)","\u67e5\u4e00\u4e0b\u4eca\u5929\u5929\u6c14\u9884\u62a5\uff0c\u5982\u679c\u4e0b\u96e8\u7684\u8bdd\uff0c\u5e2e\u6211\u627e\u4e00\u5904\u6700\u8fd1\u7684\u4f11\u606f\u9a7b\u5730"),
        # ("\u591a\u8df3\u4efb\u52a1(\u5148\u5730\u8d28\u77e5\u8bc6\u518d\u540e\u52e4)","\u8fd9\u5757\u5ca9\u77f3\u600e\u4e48\u91c囟吐？\u5982\u679c\u592a\u5371\u9669\u5904\u7406\u4e0d\u4e86\uff0c\u5c31\u76f4\u63a5\u5e2e\u6211\u5bfc\u822a\u53bb\u6700\u8fd1\u7684\u5c0f\u9547"),
    ]

    # 循环执行测试
    for name, inp in test_cases:
        await run_single_test(name, inp)

    print("\n所有测试完成！\n")


if __name__ == "__main__":
    asyncio.run(main())
