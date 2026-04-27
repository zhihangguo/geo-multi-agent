"""
SSE 取消问题测试：模拟 SSE 连接在 agent 执行中被取消的场景。

验证：即使 SSE 被取消，历史对话也应该被保存到文件。

运行：
  cd backend/app
  python test_sse_cancel.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repositories.session_repository import session_repository

TEST_USER = "test_sse_cancel"
TEST_SESSION = "test_session_cancel"


def _file_path():
    return session_repository._get_file_path(TEST_USER, TEST_SESSION)


def _cleanup():
    p = _file_path()
    if p.exists():
        p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)


def _count_messages():
    p = _file_path()
    if not p.exists():
        return 0
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return len(data)


async def old_approach():
    """旧代码：except Exception 捕获不到 CancelledError"""
    _cleanup()
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "你好"})
    process_logs = []

    try:
        # 模拟 agent 执行（被取消）
        full_history.append({"role": "assistant", "content": "部分回答"})
        await asyncio.sleep(0.05)  # 模拟延迟
        raise asyncio.CancelledError("SSE 连接已取消")
    except Exception as e:
        # CancelledError 不会被这里捕获！
        print(f"  except Exception 捕获到: {type(e).__name__}: {e}")

    # 这行永远不会执行（因为 CancelledError 跳出）
    if process_logs:
        full_history.append({"role": "process", "content": "\n".join(process_logs)})
    full_history.append({"role": "assistant", "content": "最终回答"})
    await session_repository.save_session(TEST_USER, TEST_SESSION, full_history)

    count = _count_messages()
    print(f"  旧代码保存消息数: {count} (期望 4, {'OK' if count == 4 else 'FAIL - 没保存!'})")
    return count == 4


async def new_approach():
    """新代码：finally + 捕获 CancelledError 确保保存"""
    _cleanup()
    full_history = [{"role": "system", "content": "test"}]
    full_history.append({"role": "user", "content": "你好"})
    process_logs = []
    final_answer = ""
    error_msg = ""
    cancelled = False

    try:
        full_history.append({"role": "assistant", "content": "部分回答"})
        await asyncio.sleep(0.05)
        raise asyncio.CancelledError("SSE 连接已取消")
    except asyncio.CancelledError:
        cancelled = True
        print(f"  except CancelledError 捕获到: SSE 被取消")
    except Exception as e:
        error_msg = str(e)
        print(f"  except Exception 捕获到: {e}")
    finally:
        # 无论如何都保存
        if process_logs:
            full_history.append({"role": "process", "content": "\n".join(process_logs)})
        if not final_answer and not error_msg:
            final_answer = "请求被中断，但已保存的对话不会丢失"
        if final_answer:
            full_history.append({"role": "assistant", "content": final_answer})
        await session_repository.save_session(TEST_USER, TEST_SESSION, full_history)
        if cancelled:
            # 重新抛出，让 FastAPI 知道连接被取消了
            raise

    count = _count_messages()
    print(f"  新代码保存消息数: {count} (期望 3, {'OK' if count == 3 else 'FAIL'})")
    return count == 3


async def main():
    print("=" * 70)
    print("  SSE 取消问题测试")
    print("=" * 70)

    print("\n--- 旧代码（except Exception 捕获不到 CancelledError）---")
    old_ok = await old_approach()

    print("\n--- 新代码（finally + CancelledError 捕获）---")
    new_ok = await new_approach()

    print("\n" + "=" * 70)
    print(f"  旧代码: {'FAIL' if not old_ok else 'PASS'}")
    print(f"  新代码: {'PASS' if new_ok else 'FAIL'}")
    print("=" * 70)

    _cleanup()


if __name__ == "__main__":
    asyncio.run(main())
