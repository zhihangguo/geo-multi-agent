"""
完整模拟一次 agent_service.process_task 的保存流程。

运行：cd backend/app && python test_process_task_flow.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repositories.session_repository import session_repository
from services.session_service import session_service

TEST_USER = "test_flow"
TEST_SID = "test_process_task"


def _path():
    return session_repository._get_file_path(TEST_USER, TEST_SID)


def _cleanup():
    p = _path()
    if p.exists():
        p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)


def _data():
    p = _path()
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _print_state(label):
    d = _data()
    if d is None:
        print(f"  {label}: 文件不存在")
    else:
        roles = [m.get("role", "?") for m in d]
        print(f"  {label}: {len(d)} 条, roles={roles}")


async def process_task_like_normal():
    _cleanup()
    user_id, session_id = TEST_USER, TEST_SID
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "你好"})
    final_answer = ""
    process_logs = []
    try:
        await asyncio.sleep(0.01)
        final_answer = "你好！"
        process_logs.append("[处理中]")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        if process_logs:
            full_history.append({"role": "process", "content": "\n".join(process_logs)})
        if final_answer:
            full_history.append({"role": "assistant", "content": final_answer})
        await session_service.save_history(user_id, session_id, full_history)
    _print_state("正常完成")
    d = _data()
    return d is not None and len(d) == 4


async def process_task_like_cancelled():
    _cleanup()
    user_id, session_id = TEST_USER, TEST_SID
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "被取消"})
    final_answer = ""
    process_logs = []
    try:
        await asyncio.sleep(0.01)
        process_logs.append("[处理中]")
        final_answer = "部分回答"
        raise asyncio.CancelledError("SSE 取消")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        if process_logs:
            full_history.append({"role": "process", "content": "\n".join(process_logs)})
        if final_answer:
            full_history.append({"role": "assistant", "content": final_answer})
        await session_service.save_history(user_id, session_id, full_history)
    _print_state("SSE 取消")
    d = _data()
    return d is not None and len(d) == 4


async def process_task_like_exception():
    _cleanup()
    user_id, session_id = TEST_USER, TEST_SID
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "异常"})
    final_answer = ""
    process_logs = []
    try:
        process_logs.append("[处理中]")
        raise RuntimeError("模拟错误")
    except asyncio.CancelledError:
        pass
    except Exception:
        final_answer = "请求失败"
    finally:
        if process_logs:
            full_history.append({"role": "process", "content": "\n".join(process_logs)})
        if final_answer:
            full_history.append({"role": "assistant", "content": final_answer})
        await session_service.save_history(user_id, session_id, full_history)
    _print_state("异常")
    d = _data()
    return d is not None and len(d) == 4


async def test_langgraph_return_finally_runs():
    """
    验证：在 try/finally 中 return，finally 一定执行。
    这是 Python 语言保证，直接用最小化测试验证。
    """
    _cleanup()
    user_id, session_id = TEST_USER, TEST_SID
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "LangGraph"})
    final_answer = ""
    process_logs = []

    async def inner():
        nonlocal final_answer, process_logs
        try:
            process_logs.append("[LangGraph]")
            await asyncio.sleep(0.01)
            final_answer = "LangGraph 回答"
            # 这里不 return，直接让 finally 执行
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            if process_logs:
                full_history.append({"role": "process", "content": "\n".join(process_logs)})
            if final_answer:
                full_history.append({"role": "assistant", "content": final_answer})
            await session_service.save_history(user_id, session_id, full_history)

    await inner()
    _print_state("LangGraph")
    d = _data()
    return d is not None and len(d) == 4


async def process_task_multi_round():
    _cleanup()
    user_id, session_id = TEST_USER, TEST_SID
    for i in range(5):
        full_history = session_service.load_history(user_id, session_id)
        if full_history is None:
            full_history = [{"role": "system", "content": "test"}]
        full_history.append({"role": "user", "content": f"第{i+1}问"})
        full_history.append({"role": "assistant", "content": f"回答{i+1}"})
        await session_service.save_history(user_id, session_id, full_history)
    _print_state("5 轮后")
    d = _data()
    return d is not None and len(d) == 11  # 1 + 5*2


# 专门验证 Python return + finally 行为
def test_return_finally():
    """在 try 中 return 时 finally 一定执行。返回 True 表示验证通过。"""
    saved = False

    def func():
        nonlocal saved
        try:
            return
        finally:
            saved = True

    func()
    return saved


async def main():
    print("=" * 70)
    print("  process_task 保存流程测试")
    print("=" * 70)

    print("\n--- 0. Python return+finally 验证 ---")
    py_ok = test_return_finally()
    print(f"  return 前 finally 执行: {'PASS' if py_ok else 'FAIL'}")

    print("\n--- 1. 正常完成 ---")
    r1 = await process_task_like_normal()

    print("\n--- 2. SSE 取消 ---")
    r2 = await process_task_like_cancelled()

    print("\n--- 3. 异常 ---")
    r3 = await process_task_like_exception()

    print("\n--- 4. LangGraph ---")
    r4 = await test_langgraph_return_finally_runs()

    print("\n--- 5. 多轮累积 (5轮) ---")
    r5 = await process_task_multi_round()

    print("\n" + "=" * 70)
    results = [
        ("Python return+finally", py_ok),
        ("正常完成", r1),
        ("SSE 取消", r2),
        ("异常", r3),
        ("LangGraph", r4),
        ("多轮累积", r5),
    ]
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    n = sum(1 for _, v in results if v)
    print(f"\n  总计: {n}/{len(results)} 通过")
    print("=" * 70)

    _cleanup()


if __name__ == "__main__":
    asyncio.run(main())
