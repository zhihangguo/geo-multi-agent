import os, sys, asyncio
os.environ['ANONYMIZED_TELEMETRY'] = 'false'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.memory.mem0_memory import mem0_memory
mem0_memory._initialized = False
mem0_memory._memory = None
mem0_memory._init_error = None
mem0_memory._ensure_memory()

uid = "test_add_debug"

print("=== Direct add test ===")
result = mem0_memory._memory.add("你好，我叫小米", user_id=uid)
print("add result:", result)

print("\n=== get_all ===")
all_m = mem0_memory._memory.get_all(filters={"user_id": uid})
print("get_all:", all_m)

# Now test async path matching save_history
print("\n=== Simulate save_history ===")
async def test():
    chat_history = [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好，我叫小米"},
        {"role": "assistant", "content": "你好小米！"},
    ]
    latest_user_msgs = [
        msg["content"]
        for msg in chat_history[-4:]
        if msg.get("role") == "user"
    ]
    print("user msgs to add:", latest_user_msgs)
    for text in latest_user_msgs:
        if text and len(text.strip()) > 10:
            print(f"Adding: '{text}'")
            r = mem0_memory._memory.add(text, user_id=uid)
            print(f"  result: {r}")

asyncio.run(test())

print("\n=== get_all after ===")
all_m = mem0_memory._memory.get_all(filters={"user_id": uid})
print("get_all:", all_m)

