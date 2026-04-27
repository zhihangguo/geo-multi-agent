"""
验证：全局记忆模式下，多轮问答的历史是否完整保存。

模拟连续 5 轮问答，验证每次保存后文件中的消息数是否正确。

运行：
  cd backend/app
  python test_history_persistence.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.session_service import session_service
from repositories.session_repository import session_repository

TEST_USER = "test_history_persist"
TEST_SESSION = "test_session_full_history"


def _file_path():
    return session_repository._get_file_path(TEST_USER, TEST_SESSION)


def _cleanup():
    """清理测试文件"""
    p = _file_path()
    if p.exists():
        p.unlink()
    # 确保用户目录存在
    p.parent.mkdir(parents=True, exist_ok=True)


def _count_messages():
    """返回文件中的消息总数（含 system）"""
    p = _file_path()
    if not p.exists():
        return 0
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return len(data)


def _print_messages():
    """打印文件中的每条消息"""
    p = _file_path()
    if not p.exists():
        print("  文件不存在")
        return
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  文件中共 {len(data)} 条消息:")
    for i, msg in enumerate(data):
        role = msg.get("role", "?")
        content = msg.get("content", "")[:60]
        print(f"    [{i}] {role}: {content}...")


async def simulate_round(round_num: int, query: str):
    """模拟一轮问答：prepare_history -> LLM（跳过） -> save_history"""
    print(f"\n--- 第 {round_num} 轮: '{query}' ---")

    # Step 1: prepare_history（截断版给 LLM）
    chat_history_for_llm = session_service.prepare_history(
        TEST_USER, TEST_SESSION, query,
        memory_mode="file", memory_scope="global"
    )
    print(f"  prepare_history 返回 {len(chat_history_for_llm)} 条（给 LLM 的截断版）")

    # Step 2: load_history（完整版用于保存）
    full_history = session_service.load_history(TEST_USER, TEST_SESSION)
    if full_history is None:
        full_history = [{"role": "system", "content": f"系统消息 (会话 {TEST_SESSION})"}]
    full_history.append({"role": "user", "content": query})

    # Step 3: 模拟 LLM 回答
    answer = f"这是第 {round_num} 轮的回答"
    full_history.append({"role": "assistant", "content": answer})

    # Step 4: 保存
    await session_service.save_history(TEST_USER, TEST_SESSION, full_history)

    # Step 5: 验证文件
    count = _count_messages()
    expected = 1 + round_num * 2  # 1 system + (user + assistant) * rounds
    status = "OK" if count == expected else f"FAIL (期望 {expected})"
    print(f"  文件消息数: {count} [{status}]")
    _print_messages()

    return count == expected


async def main():
    print("=" * 70)
    print("  全局记忆持久化测试")
    print("=" * 70)

    _cleanup()

    queries = [
        "你好",
        "今天的天气怎么样",
        "帮我规划一下从北京到上海的路线",
        "推荐一些好吃的",
        "总结一下我们的对话",
    ]

    results = []
    for i, q in enumerate(queries, 1):
        ok = await simulate_round(i, q)
        results.append(ok)

    # 汇总
    print("\n" + "=" * 70)
    print("  测试结果")
    print("=" * 70)
    for i, ok in enumerate(results, 1):
        status = "PASS" if ok else "FAIL"
        print(f"  第 {i} 轮: [{status}]")

    total = len(results)
    passed = sum(results)
    print(f"\n  总计: {passed}/{total} 通过")

    if passed == total:
        print("\n  历史消息已完整保存，全局记忆功能正常!")
    else:
        print("\n  存在消息丢失问题!")

    # 清理
    _cleanup()


if __name__ == "__main__":
    asyncio.run(main())
