import os, sys, asyncio
os.environ['ANONYMIZED_TELEMETRY'] = 'false'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.memory.mem0_memory import mem0_memory

# Force clean init
mem0_memory._initialized = False
mem0_memory._memory = None
mem0_memory._init_error = None

uid = "test_flow_root1"

# Step 1: prepare_history (initializes mem0)
print("=== Step 1: prepare_history ===")
history = mem0_memory.prepare_history(uid, "session1", "你好，我是小米")
print("History:")
for msg in history:
    print(f"  [{msg['role']}]: {msg['content'][:120]}")

# Step 2: save_history
print("\n=== Step 2: save_history ===")
asyncio.run(mem0_memory.save_history(uid, "session1", [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好，我叫小米"},
    {"role": "assistant", "content": "你好小米！"},
]))
print("save_history done")

# Step 3: prepare_history with query
print("\n=== Step 3: prepare_history (query) ===")
history2 = mem0_memory.prepare_history(uid, "session2", "我叫什么？")
print("History:")
for msg in history2:
    content = msg['content']
    if len(content) > 200:
        content = content[:200] + "..."
    print(f"  [{msg['role']}]: {content}")


# Step 4: Check raw mem0 storage
print("\n=== Step 4: Check raw storage ===")
all_m = mem0_memory._memory.get_all(filters={"user_id": uid})
print("get_all:", all_m)

