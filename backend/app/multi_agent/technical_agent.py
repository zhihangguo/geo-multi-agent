from infrastructure.ai.prompt_loader import load_prompt
from infrastructure.ai.openai_client import sub_model
from infrastructure.tools.local.knowledge_base import query_knowledge_tool
from infrastructure.tools.mcp.web_search_tool import web_search_tool
from infrastructure.tools.mcp.mcp_servers import search_mcp_client
from agents import Agent, ModelSettings
from agents import Runner,RunConfig


# 1. 定义地质知识智能体
technical_agent = Agent(
    name="地质知识专家",
    instructions=load_prompt("technical_agent"),
    model=sub_model,
    model_settings=ModelSettings(temperature=0),  # 不要发挥内容(软件层面限制模型的发挥)
    tools=[query_knowledge_tool, web_search_tool],
    mcp_servers=[search_mcp_client],
)


# 2. 测试技术智能体
async def run_single_test(case_name: str, input_text: str):

    print(f"\n{'=' * 80}")
    print(f"测试用例: {case_name}")
    print(f"输入: \"{input_text}\"")
    print("-" * 80)
    try:
        await search_mcp_client.connect()
        print("思考中...")
        result = await Runner.run(technical_agent, input=input_text,run_config=RunConfig(tracing_disabled=True))
        print(f"\n\nAgent的最终输出: {result.final_output}")
    except Exception as e:
        print(f"\n Error: {e}\n")
    finally:
        try:
            await search_mcp_client.cleanup()
        except:
            pass


async def main():
    # 地质知识测试案例
    test_cases = [
        # ("Case 1: 地质专业知识", "野外如何快速鉴定石英和长石的区别？"),
        # ("Case 2: 实时资讯", "今天作业区附近的天气怎么样？"),
        # ("Case 3: 应拒绝", "帮我找一下最近的补给点"),  # 应拒绝（后勤导航类）
        # ("Case 3: 应拒绝", "花岗岩的颜色是什么？"),
        ("Case 4: 闲聊", "你好啊，我今天真的很不开心，你有什么想对我说"),  # 应拒绝
    ]

    for name, question in test_cases:
        await run_single_test(name, question)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

