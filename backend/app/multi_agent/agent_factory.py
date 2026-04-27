from agents import function_tool, Runner
from agents.run import RunConfig

from multi_agent.technical_agent import technical_agent
from multi_agent.service_agent import comprehensive_service_agent
from multi_agent_autopilot.agent import autopilot_agent
from infrastructure.logging.logger import logger


# 1. 定义技术专家智能体工具
@function_tool
async def consult_technical_expert(
        query: str,
) -> str:
    """
    【咨询技术专家】处理地质专业知识、技术咨询以及实时资讯（如天气、新闻、地震速报）。
    当用户询问：
    1. 地质专业问题："岩石鉴定"、"矿物识别"、"地层划分"、"构造分析"等。
    2. 实时信息："今天天气"、"地震速报"、"最新科研成果"等。
    请调用此工具。

    Args:
        query: 用户的原始问题或完整指令。
    """
    try:
        logger.info(f"[Route] 转交技术专家: {query[:30]}...")

        # 直接委托给 technical_agent，让它自己决定使用知识库还是联网搜索
        # technical_agent 现在同时拥有 query_knowledge_tool 和 web_search_tool
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
        logger.error(f"技术专家执行异常: {e}")
        return f"技术专家暂时无法回答: {str(e)}"


# 2. 定义全能业务智能体工具
@function_tool
async def query_service_station_and_navigate(
        query: str,
) -> str:
    """
        【野外后勤导航专家】处理线下服务站查询、位置查找和地图导航需求。
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
        # 注意：MCP 连接已在 agent_service.py 请求入口通过 MCPSessionManager 统一建立
        result = await Runner.run(
            comprehensive_service_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )
        return result.final_output
    except Exception as e:
        return f"业务专家暂时无法回答: {str(e)}"


# 3. 定义自动驾驶评估专家工具
@function_tool
async def consult_autopilot_expert(
        query: str,
        tenant_id: str = "tenant_a",
) -> str:
    """
    【自动驾驶评估专家】处理自动驾驶数据分析、评估报告、安全统计等需求。
    当用户询问：
    1. 测试数据查询："查询 AV-001 的所有测试记录"、"雨天场景的感知指标"
    2. 安全事件统计："统计各严重级别的安全事件数量"
    3. 日志分析："分析 RUN-001 的系统日志"
    4. 评估报告："生成 RUN-001 的评估报告"
    5. 语义搜索："找出感知表现最差的几次测试"
    请调用此工具。

    Args:
        query: 用户的原始问题或完整指令。
    """
    try:
        logger.info(f"[Route] 转交自动驾驶评估专家: {query[:30]}...")
        result = await Runner.run(
            autopilot_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )
        output = result.final_output
        if output is None:
            return "自动驾驶评估专家已执行，但未返回可展示文本。"
        return str(output).strip() or "自动驾驶评估专家已执行，但返回内容为空。"
    except Exception as e:
        logger.error(f"自动驾驶评估专家执行异常: {e}")
        return f"自动驾驶评估专家暂时无法回答: {str(e)}"


# 4. 将三个工具暴露出去
AGENT_TOOLS = [
    consult_technical_expert,
    query_service_station_and_navigate,
    consult_autopilot_expert,
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
