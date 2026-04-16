from agents import function_tool, Runner
from agents.run import RunConfig

from multi_agent.technical_agent import technical_agent
from multi_agent.service_agent import comprehensive_service_agent
from infrastructure.tools.mcp.mcp_servers import search_mcp_client, baidu_mcp_client
from infrastructure.tools.mcp.mcp_manager import mcp_connect, mcp_cleanup

from infrastructure.logging.logger import logger
from infrastructure.tools.local.knowledge_base import query_knowledge


# 1. 定义技术专家智能体工具
@function_tool
async def consult_technical_expert(
        query: str,
) -> str:
    """
    【咨询与技术专家】处理技术咨询、设备故障、维修建议以及实时资讯（如股价、新闻、天气）。
    当用户询问：
    1. "怎么修"、"为什么坏了"、"如何操作"等技术问题。
    2. "今天股价"、"现在天气"等实时信息。
    请调用此工具。

    Args:
    query: 用户的原始问题或完整指令。
    """
    try:
        logger.info(f"[Route] 转交技术专家: {query[:30]}...")

        # 稳态优先：先直连知识库，避免Agent工具链在当前环境下出现无输出/取消问题
        kb_result = await query_knowledge(question=query)
        if isinstance(kb_result, dict):
            kb_answer = str(kb_result.get("answer", "")).strip()
            if kb_answer:
                return kb_answer

            kb_err = str(kb_result.get("error_msg", "")).strip()
            if kb_err:
                # 对地质知识问题，不再回退到技术专家Agent，直接返回清晰错误，避免兜圈子/空回复
                if any(keyword in query for keyword in ["岩石", "矿物", "地层", "构造", "鉴定", "地质"]):
                    return f"知识库暂时不可用，请稍后重试。详细原因：{kb_err}"
                logger.warning(f"知识库直连失败，回退技术专家Agent: {kb_err}")

        # 仅对非知识库类问题回退到技术专家Agent（可覆盖实时资讯等场景）
        await mcp_connect()
        result = await Runner.run(
            technical_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )
        output = result.final_output
        if output is None:
            return "技术专家已执行，但未返回可展示文本。"
        output = str(output).strip()
        return output or "技术专家已执行，但返回内容为空。"
    except Exception as e:
        return f"技术专家暂时无法回答: {str(e)}"
    finally:
        await mcp_cleanup()


# 2. 定义全能业务智能体工具
@function_tool
async def query_service_station_and_navigate(
        query: str,
) -> str:
    """
        【服务站专家】处理线下服务站查询、位置查找和地图导航需求。
        当用户询问：
        1. "附近的维修点"、"找小米之家"（服务站查询）。
        2. "怎么去XX"、"导航到XX"（路径规划）。
        3. 任何涉及地理位置和线下门店的请求。
        请调用此工具。
        Args:
            query: 用户的原始问题（包含隐含的位置信息）。
    """
    try:
        logger.info(f"[Route] 转交业务专家: {query[:30]}...")
        await mcp_connect()
        result = await Runner.run(
            comprehensive_service_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )
        return result.final_output
    except Exception as e:
        return f"业务专家暂时无法回答: {str(e)}"
    finally:
        await mcp_cleanup()


# 3. 将两个工具暴露出去
AGENT_TOOLS = [
    consult_technical_expert,
    query_service_station_and_navigate
]


async def run_technical_tool():
    """测试技术专家工具"""
    print("\n" + "=" * 80)
    print("测试技术专家Agent Tool")
    print("=" * 80)
    await search_mcp_client.connect()

    test_cases = ["今天小米股价多少"]

    for query in test_cases:
        print(f"\n 查询: {query}")
        print("-" * 0)
        result = await consult_technical_expert(query=query)
        print(f"回答: {result}\n")

    await search_mcp_client.cleanup()


async def run_service_tool():
    """测试业务服务工具"""
    print("\n" + "=" * 80)
    print("测试业务服务Agent Tool")
    print("=" * 80)

    await baidu_mcp_client.connect()

    test_cases = [
        # "我想去小米之家修电脑",
        "怎么去颐和园",
    ]

    for query in test_cases:
        print(f"\n查询: {query}")
        print("-" * 80)
        result = await query_service_station_and_navigate(query=query)
        print(f"回答: {result}\n")

    await baidu_mcp_client.cleanup()


async def main():
    # 1. 测试技术智能体工具
    # await run_technical_tool()

    # 2. 测试全能业务智能体工具
    await run_service_tool()
    # print("\n所有测试完成！\n")


# 以下是测试代码，可以独立运行测试每个Agent Tool
if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
