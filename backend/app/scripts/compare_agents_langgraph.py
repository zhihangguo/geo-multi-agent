import asyncio
import json
from typing import List

import httpx

API_URL = "http://127.0.0.1:8000/api/query"

TEST_CASES: List[str] = [
    "花岗岩和闪长岩如何区分？",
    "今天作业区附近天气如何？",
    "帮我找最近的补给点",
    "怎么去最近的医疗站？",
]


def build_payload(query: str, mode: str, user_id: str = "root1"):
    return {
        "query": query,
        "context": {
            "user_id": user_id,
            "session_id": ""
        },
        "mode": mode
    }


async def run_single(query: str, mode: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(API_URL, json=build_payload(query, mode))
        response.raise_for_status()
        content = await response.aread()
        return content.decode("utf-8")


async def main():
    results = []
    for query in TEST_CASES:
        agents_result = await run_single(query, "agents")
        langgraph_result = await run_single(query, "langgraph")

        results.append({
            "query": query,
            "agents": agents_result,
            "langgraph": langgraph_result
        })

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
