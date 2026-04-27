"""
一次性清理脚本：删除 ChromaDB 中所有英文记忆条目。

这些条目是 mem0 在 infer=True 模式下产生的（如 "User's name is 小白"），
会干扰 FactExtractor 的冲突检测和检索质量。

使用方法：
    cd backend/app
    python scripts/clean_english_memories.py

安全说明：
- 仅删除包含英文关键词（User/user's/currently called）的记忆
- 会先列出将被删除的条目，确认后才会执行
- 不会删除任何中文记忆
"""
import sys
import os

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from services.memory.mem0_memory import mem0_memory
from infrastructure.logging.logger import logger


def find_english_memories(user_id: str = None) -> list:
    """找出所有英文记忆条目。"""
    mem0_memory._ensure_memory()

    if user_id:
        user_ids = [user_id]
    else:
        # 获取所有已知用户
        user_ids = list(mem0_memory._user_memories.keys())
        if mem0_memory._memory:
            user_ids.append("default")

    english_memories = []

    for uid in user_ids:
        try:
            all_memories = mem0_memory.get_all_memories(uid, top_k=500)
            for mem in all_memories:
                text = mem.get("memory", "")
                # 匹配 mem0 infer 模式产生的英文
                if any(marker in text for marker in [
                    "User", "user's", "User's", "user is",
                    "currently called", "mentioned they",
                    "introduced their", "changed their",
                    "updated their", "set their",
                    "goes by", "uses "
                ]):
                    english_memories.append({
                        "user_id": uid,
                        "id": mem.get("id", ""),
                        "memory": text,
                    })
        except Exception as e:
            logger.warning(f"获取用户 {uid} 的记忆失败: {e}")

    return english_memories


def clean_english_memories(user_id: str = None, dry_run: bool = True):
    """清理英文记忆。"""
    english_memories = find_english_memories(user_id)

    if not english_memories:
        print("没有找到英文记忆，无需清理。")
        return

    print(f"\n{'=' * 60}")
    print(f"发现 {len(english_memories)} 条英文记忆：")
    print(f"{'=' * 60}")

    for i, mem in enumerate(english_memories, 1):
        print(f"\n{i}. [{mem['user_id']}] {mem['memory']}")
        print(f"   ID: {mem['id'][:12]}...")

    print(f"\n{'=' * 60}")

    if dry_run:
        print(f"【预览模式】以上 {len(english_memories)} 条将被删除。")
        print("如需实际执行，请再次运行（或传入 --confirm 参数）。")
        return

    print("\n开始清理...")
    deleted = 0
    for mem in english_memories:
        try:
            user_memory = mem0_memory._get_user_memory(mem["user_id"])
            if user_memory:
                user_memory.delete(mem["id"])
                deleted += 1
        except Exception as e:
            logger.warning(f"删除记忆 {mem['id'][:8]} 失败: {e}")

    print(f"清理完成！共删除 {deleted}/{len(english_memories)} 条英文记忆。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="清理 ChromaDB 中的英文记忆")
    parser.add_argument("--user-id", help="指定用户 ID（默认清理所有用户）")
    parser.add_argument("--confirm", action="store_true", help="确认执行删除（默认只预览）")
    args = parser.parse_args()

    clean_english_memories(user_id=args.user_id, dry_run=not args.confirm)
