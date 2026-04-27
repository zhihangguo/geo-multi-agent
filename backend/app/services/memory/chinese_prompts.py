"""
Fork of mem0 ADDITIVE_EXTRACTION_PROMPT — Chinese version.

Purpose: If we ever switch from application-layer LLM extraction to mem0-native
extraction, this prompt ensures the output is in Chinese and supports
UPDATE/DELETE actions (not just ADD).

Current status: NOT actively used. The application uses LLMFactExtractor in
mem0_memory.py instead. This file is kept as a reference and for future migration.

Source: D:/Desktop/文档与文件/code/mem0-main/mem0/configs/prompts.py
"""

CHINESE_ADDITIVE_EXTRACTION_PROMPT = """
# 角色

你是一个记忆提取专家。你的任务是从对话中提取所有有价值的长期记忆信息。

你从**用户和助手**双方的消息中提取：
- **用户消息**：个人信息、偏好、计划、经历、隐含偏好
- **助手消息**：给出的具体建议、方案、推荐、研究结论

## 提取原则

1. **只提取长期有效的事实**，不是短期信息或一次性内容
2. **用中文输出**，所有提取的记忆必须使用中文
3. **自包含**：每条记忆独立可理解，不使用代词
4. **简洁但完整**：15-50字，1-2句话
5. **时间锚定**：将相对时间转换为绝对日期（如"上周" → "2025年3月8日"）
6. **保留具体细节**：不将具体名词泛化为类别（如"AV-001设备"不要泛化为"设备"）

## 事实类别

- name: 用户的名字/称呼
- location: 用户的位置/居住地
- preference: 用户的偏好/喜好
- occupation: 用户的职业/工作内容
- equipment: 用户使用的设备/工具
- project: 用户参与的项目/任务
- advice: 助手给出的建议/推荐
- solution: 助手提供的解决方案
- context: 助手提供的背景信息
- plan: 用户或助手的计划/安排
- observation: 观察到的用户行为模式

## 操作类型（扩展：支持更新和删除）

与 mem0 原版不同，本版本支持三种操作：
- **add**: 添加新记忆（默认）
- **update**: 更新已有记忆（同一事实的新版本，提供 target_memory_id）
- **delete**: 删除过时记忆（提供 target_memory_id）

## 输出格式

严格返回 JSON 对象，包含 "memory" 数组：

{
  "memory": [
    {
      "action": "add",
      "text": "记忆内容（中文）",
      "category": "事实类别",
      "attributed_to": "user" 或 "assistant"
    },
    {
      "action": "update",
      "target_memory_id": "已有记忆的UUID",
      "text": "更新后的记忆内容（中文）"
    },
    {
      "action": "delete",
      "target_memory_id": "需删除的已有记忆UUID",
      "reason": "删除原因"
    }
  ]
}

## 示例1：基本信息提取

用户："我叫小黑，最近在昆明做地质调查"
助手："建议使用便携式 XRF 分析仪，昆明附近有多个地质观测点"

输出：
{
  "memory": [
    {"action": "add", "text": "用户的名字是小黑", "category": "name", "attributed_to": "user"},
    {"action": "add", "text": "用户最近在昆明从事地质调查工作", "category": "occupation", "attributed_to": "user"},
    {"action": "add", "text": "建议用户使用便携式 XRF 分析仪进行地质调查", "category": "advice", "attributed_to": "assistant"}
  ]
}

## 示例2：冲突更新

已有记忆：[{"id": "uuid-123", "text": "用户的名字是小黑"}]
用户："我改名叫小白了"

输出：
{
  "memory": [
    {"action": "update", "target_memory_id": "uuid-123", "text": "用户的名字是小白", "category": "name", "attributed_to": "user"},
    {"action": "delete", "target_memory_id": "uuid-123", "reason": "名字已更新为小白"}
  ]
}

## 示例3：无有价值的事实

用户："你好"
助手："你好！有什么可以帮助你的？"

输出：{"memory": []}

## 对话

{conversation}

请提取事实，返回 JSON 对象（不要返回其他内容）：
"""


def generate_chinese_extraction_prompt(
    conversation: str,
    custom_instructions: str = None,
) -> str:
    """
    构建中文事实提取 prompt。

    Args:
        conversation: 格式化的对话文本
        custom_instructions: 自定义指令（可选）

    Returns:
        完整的 prompt 文本
    """
    prompt = CHINESE_ADDITIVE_EXTRACTION_PROMPT.format(conversation=conversation)
    if custom_instructions:
        prompt += f"\n\n## 自定义指令\n{custom_instructions}"
    return prompt
