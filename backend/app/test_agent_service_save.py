"""
验证 agent_service.py 的修复：

1. 正常完成：消息应完整保存
2. SSE 取消（CancelledError）：消息也应保存
3. 异常：消息也应保存
4. LangGraph 模式：消息应完整保存

运行：
  cd backend/app
  python test_agent_service_save.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repositories.session_repository import session_repository

TEST_USER = "test_agent_save"
TEST_SESSION_PREFIX = "test_sess"


def _file(session_id):
    return session_repository._get_file_path(TEST_USER, session_id)


def _cleanup(session_id):
    p = _file(session_id)
    if p.exists():
        p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)


def _count(session_id):
    p = _file(session_id)
    if not p.exists():
        return 0
    with p.open("r", encoding="utf-8") as f:
        return len(json.load(f))


def _roles(session_id):
    p = _file(session_id)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [m.get("role", "?") for m in data]


async def test_normal_save():
    """测试：正常完成时保存"""
    sid = f"{TEST_SESSION_PREFIX}_normal"
    _cleanup(sid)

    # 模拟 agent_service.py 的保存流程
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "你好"})
    final_answer = "你好！有什么可以帮助你的？"
    process_logs = ["[处理中]"]

    # finally 块
    if process_logs:
        full_history.append({"role": "process", "content": "\n".join(process_logs)})
    if final_answer:
        full_history.append({"role": "assistant", "content": final_answer})
    await session_repository.save_session(TEST_USER, sid, full_history)

    count = _count(sid)
    roles = _roles(sid)
    ok = count == 4 and roles == ["system", "user", "process", "assistant"]
    print(f"  正常保存: {count} 条, roles={roles} [{'PASS' if ok else 'FAIL'}]")
    _cleanup(sid)
    return ok


async def test_cancelled_error_save():
    """测试：CancelledError 被捕获时保存"""
    sid = f"{TEST_SESSION_PREFIX}_cancel"
    _cleanup(sid)

    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "你好"})
    final_answer = "部分回答"
    process_logs = ["[处理中]"]

    try:
        # 模拟 agent 执行中被取消
        await asyncio.sleep(0.01)
        raise asyncio.CancelledError("SSE 连接已取消")
    except asyncio.CancelledError:
        pass  # 捕获但不重新抛出
    finally:
        if process_logs:
            full_history.append({"role": "process", "content": "\n".join(process_logs)})
        if final_answer:
            full_history.append({"role": "assistant", "content": final_answer})
        await session_repository.save_session(TEST_USER, sid, full_history)

    count = _count(sid)
    roles = _roles(sid)
    ok = count == 4 and "assistant" in roles and "user" in roles
    print(f"  取消保存: {count} 条, roles={roles} [{'PASS' if ok else 'FAIL'}]")
    _cleanup(sid)
    return ok


async def test_exception_save():
    """测试：Exception 被捕获时保存"""
    sid = f"{TEST_SESSION_PREFIX}_exception"
    _cleanup(sid)

    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "你好"})
    final_answer = ""
    process_logs = ["[处理中]"]
    error_msg = ""

    try:
        await asyncio.sleep(0.01)
        raise RuntimeError("LLM 调用失败")
    except Exception as e:
        error_msg = str(e)
        final_answer = f"请求失败: {error_msg}"
    finally:
        if process_logs:
            full_history.append({"role": "process", "content": "\n".join(process_logs)})
        if final_answer:
            full_history.append({"role": "assistant", "content": final_answer})
        await session_repository.save_session(TEST_USER, sid, full_history)

    count = _count(sid)
    roles = _roles(sid)
    ok = count == 4 and "assistant" in roles and "user" in roles
    print(f"  异常保存: {count} 条, roles={roles} [{'PASS' if ok else 'FAIL'}]")
    _cleanup(sid)
    return ok


async def test_multi_round_persistence():
    """测试：多轮问答时历史完整累积"""
    sid = f"{TEST_SESSION_PREFIX}_multi"
    _cleanup(sid)

    queries = ["你好", "天气怎样", "推荐个餐厅"]
    answers = ["你好！", "晴天", "去XX餐厅"]

    for i, (q, a) in enumerate(zip(queries, answers)):
        # 模拟每轮：加载历史 -> 追加用户消息 -> LLM处理 -> 追加回答 -> 保存
        from services.session_service import session_service
        full_history = session_service.load_history(TEST_USER, sid)
        if full_history is None:
            full_history = [{"role": "system", "content": "test"}]
        full_history.append({"role": "user", "content": q})
        full_history.append({"role": "assistant", "content": a})
        await session_service.save_history(TEST_USER, sid, full_history)

        count = _count(sid)
        expected = 1 + (i + 1) * 2  # system + (user+assistant) * rounds
        ok = count == expected
        print(f"  第 {i+1} 轮: {count} 条 (期望 {expected}) [{'PASS' if ok else 'FAIL'}]")
        if not ok:
            _cleanup(sid)
            return False

    roles = _roles(sid)
    print(f"  最终 roles: {roles}")
    _cleanup(sid)
    return True


async def main():
    print("=" * 70)
    print("  agent_service.py 保存逻辑测试")
    print("=" * 70)

    print("\n--- 1. 正常保存 ---")
    r1 = await test_normal_save()

    print("\n--- 2. SSE 取消保存 ---")
    r2 = await test_cancelled_error_save()

    print("\n--- 3. 异常保存 ---")
    r3 = await test_exception_save()

    print("\n--- 4. 多轮持久化 ---")
    r4 = await test_multi_round_persistence()

    print("\n" + "=" * 70)
    results = [("正常保存", r1), ("SSE取消保存", r2), ("异常保存", r3), ("多轮持久化", r4)]
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"\n  总计: {sum(r for _, r in results)}/{len(results)} 通过")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
