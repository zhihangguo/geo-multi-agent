import asyncio
import httpx
from typing import Dict
from agents import function_tool
from infrastructure.logging.logger import logger
from config.settings import settings


async def query_knowledge_raw(question: str) -> Dict:
    """
       查询地质专业知识库服务，用于检索与用户地质问题相关的专业文档或解决方案。

       Args:
           question (Optional[str]): 需要查询的具体地质问题文本（如岩石鉴定、矿物识别、地层划分等）。

       Returns:
           dict: 包含查询结果的字典。包含 'question':用户输入问题 'answer':答案
    """

    async with httpx.AsyncClient(trust_env=False) as client:
        try:
            # 1. 发送请求（异步上下文管理器对象）
            response = await client.post(
                url=f"{settings.KNOWLEDGE_BASE_URL}/query",
                json={"question": question},
                timeout=httpx.Timeout(90.0, connect=10.0),
            )

            # 2. 处理异常情况(4xx-600x)直接抛出异常
            response.raise_for_status()

            # 3. 处理正常情况（统一返回结构，便于Agent稳定消费）
            data = response.json()
            return {
                "status": "ok",
                "question": data.get("question", question),
                "answer": data.get("answer", ""),
            }

        except httpx.HTTPStatusError as e:
            body = e.response.text if e.response is not None else ""
            logger.error(
                f"知识库HTTP状态异常: url={settings.KNOWLEDGE_BASE_URL}/query, "
                f"status={e.response.status_code if e.response else 'unknown'}, body={body}, err={repr(e)}"
            )
            return {
                "status": "error",
                "question": question,
                "answer": "",
                "error_msg": f"知识库HTTP状态异常: {repr(e)}",
            }
        except httpx.RequestError as e:
            logger.error(
                f"知识库连接异常: url={settings.KNOWLEDGE_BASE_URL}/query, err={repr(e)}"
            )
            return {
                "status": "error",
                "question": question,
                "answer": "",
                "error_msg": f"知识库连接异常: {repr(e)}",
            }
        except Exception as e:
            logger.error(f"知识库未知错误: {repr(e)}")
            return {
                "status": "error",
                "question": question,
                "answer": "",
                "error_msg": f"知识库未知错误: {repr(e)}",
            }


@function_tool
async def query_knowledge(question: str) -> Dict:
    return await query_knowledge_raw(question=question)


async def main():
    result = await query_knowledge_raw(question="花岗岩和闪长岩如何区分？")
    print(result)


# 测试接口调用
if __name__ == '__main__':
    asyncio.run(main())
