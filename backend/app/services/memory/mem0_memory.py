"""
mem0-based memory strategy — three-level memory (short-term, long-term, semantic).

Uses mem0ai library with Chroma as the vector store backend.
配置从 app 的 Settings 自动读取（SF_API_KEY / SF_BASE_URL / 模型名）。

多用户隔离：每个用户拥有独立的 Chroma collection，物理隔离数据。

## 核心去重策略（三层防护）

### 第一层：LLM 事实提取 + 分类冲突检测（保存时）
用中文 LLM 从完整对话（用户+助手）中提取事实，按类别处理：
- CONFLICT 类型（name/location/preference/occupation/equipment/project）：
  同一类别不同值 → 删旧存新，确保"同一事实只有一个版本"
- NON-CONFLICT 类型（advice/solution/context/plan/observation）：
  直接存储，不做冲突检测（助手可能给出多个建议）

当前支持的事实类别见 `CONFLICT_FACT_TYPES` 和 `NON_CONFLICT_TYPES`。

如果 LLM 提取失败，回退到正则模板提取（`extract_facts`）。

### 第二层：语义去重（score > 0.92）
当新文本与已有记忆的语义高度相似时（同一事实的重复表述），
update 已有记忆而非 add 新条目。

### 第三层：检索时冲突消解（发送给 LLM 前）
从 mem0 检索到多条记忆后，对同一事实的不同版本保留最新的一条，
确保 LLM 不会收到矛盾信息。

## 关键设计决策：infer=False

mem0 的 add() 默认使用 infer=True，会调用 LLM 将输入提取并重写为英文
（如"我叫小黑黑" → "User changed their name to 小黑黑"）。
这导致：
1. 记忆语言不一致（中英文混合）
2. 中文 FactExtractor 模式无法匹配英文记忆
3. 冲突检测失败

我们使用 infer=False 绕过 mem0 的 LLM 处理，直接存储原始中文文本。
"""
import asyncio
import copy
import functools
import json
import os
import re
import stat
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from json import JSONDecodeError
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# 禁用 Chroma 遥测
os.environ["ANONYMIZED_TELEMETRY"] = "false"

from infrastructure.logging.logger import logger
from repositories.session_repository import session_repository
from services.memory.base import MemoryStrategy

MEM0_ADD_TIMEOUT_SECONDS = 45
MEM0_SEARCH_TIMEOUT_SECONDS = 10
MEM0_LIST_TIMEOUT_SECONDS = 8


# ------------------------------------------------------------------
# 结构化事实提取器（双语：中文 + 英文）
# ------------------------------------------------------------------

# mem0 的 infer 模式会重写为英文，我们需要同时匹配中英文
MEMORY_PREFIX = "以下是关于用户的信息，请用中文记录："

NAME_PATTERNS = [
    r"我(?:现在)?(?:改名|改名字).*?(?:叫|叫做|想叫|想叫做)\s*([^，。！？!?、\s]+)",
    r"(?:我叫|叫我|称呼我|我的名字是|名字是)(?!什么|啥|谁)\s*([^，。！？!?、\s]+)",
    r"我(?:现在)?想叫(?:做)?\s*([^，。！？!?、\s]+)",
    r"用户当前名字是\s*([^，。！？!?、\s]+)",
    r"用户(?:现在|目前|当前)?(?:的)?(?:名字|名称)?(?:叫|是|为)(.+?)(?:[。.!！,，\s]|$)",
    r"用户(?:现在|目前|当前)?想(?:改名|改名叫|改为|以后被称呼为|以后被叫做|被这样称呼)(?:叫|为)?(.+?)(?:[，,。.!！\s]|$)",
    r"(?:我|本人)(?:的)?(?:名字|名称)?(?:叫|是|为)(.+?)(?:[。.!！,，\s]|$)",
    r"(?:叫我|喊我|称呼我为|以后叫我|以后称呼我为)(.+?)(?:[。.!！,，\s]|$)",
    r"(?:改名|改名为|改名叫|改为)(.+?)(?:[。.!！,，\s]|$)",
    r"(?:User|user)'?s name is\s+(.+?)(?:[.!,?\s]|$)",
    r"(?:User|user)'?s current name is\s+(.+?)(?:\s+as of|[.!,?]|$)",
    r"User introduced (?:their|a) new name as\s+(.+?)(?:\s*\(|[.!,?]|$)",
    r"User (?:changed their|updated their|set their) name to\s+(.+?)(?:[.!,?\s]|$)",
    r"User (?:is|was) called?\s+(.+?)(?:[.!,?\s]|$)",
    r"User (?:goes by|uses)\s+(.+?)(?:[.!,?\s]|$)",
    r"currently called?\s+(.+?)(?:[.!,?\s]|$)",
]

FACT_TYPES = {
    "name": {
        "patterns": [
            # 中文模式
            (r"我(?:的)?名[字称]?[叫是]为?(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"(?:叫我|喊我)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"用户(?:的)?名[字称]?[叫是]为?(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"(?:改名|改名为?|改为?)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"以后叫(.+?)(?:[。.!！,，\s]|$)", 0),
            # 英文模式（mem0 infer=True 重写后的格式）
            (r"(?:User|user)'?s name is\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"User introduced (?:their|a) new name as\s+(.+?)(?:\s*\(|[.!,?]|$)", 0),
            (r"User (?:changed their|updated their|set their) name to\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"User (?:is|was) called?\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"User (?:goes by|uses)\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"currently called?\s+(.+?)(?:[.!,?\s]|$)", 0),
        ],
    },
    "location": {
        "patterns": [
            (r"我(?:在|住(?:在)?|来自|家[在]?)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"用户(?:现在|目前|当前)?(?:在|住(?:在)?)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"User (?:is|lives|works) (?:in|at|from)\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"User's location is\s+(.+?)(?:[.!,?\s]|$)", 0),
        ],
    },
    "preference": {
        "patterns": [
            (r"我(?:喜欢|偏好|常用|爱用)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"我(?:不喜欢|讨厌|不用|不爱用)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"用户(?:的)?偏好(?:是|为)?(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"User (?:likes|prefers|enjoys|uses)\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"User (?:dislikes|hates|avoids|doesn't use)\s+(.+?)(?:[.!,?\s]|$)", 0),
        ],
    },
    "occupation": {
        "patterns": [
            (r"我(?:是|从事|做|担任)(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"用户(?:的)?(?:职业|工作|岗位)(?:是|为)?(.+?)(?:[。.!！,，\s]|$)", 0),
            (r"User (?:is|works as|works in)\s+(.+?)(?:[.!,?\s]|$)", 0),
            (r"User's (?:occupation|job|profession|role) is\s+(.+?)(?:[.!,?\s]|$)", 0),
        ],
    },
}


def extract_facts(text: str) -> List[Tuple[str, str]]:
    """
    从文本中提取结构化事实（支持中英文）。

    Returns:
        [(fact_type, value), ...]
        例如: [("name", "小白"), ("name", "小黑")]
    """
    # 移除 mem0 前缀（如果存在）
    if text.startswith(MEMORY_PREFIX):
        text = text[len(MEMORY_PREFIX):]

    facts = []
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = _normalize_fact_value(match.group(1))
            if value:
                return [("name", value)]

    for fact_type, config in FACT_TYPES.items():
        for pattern, group_idx in config["patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = _normalize_fact_value(match.group(group_idx + 1))
                if value and len(value) > 0:
                    facts.append((fact_type, value))
                    break  # 每个事实类型只匹配一次
    return facts


def _normalize_fact_value(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    value = re.sub(r"^(叫|为|是|成|成为)", "", value).strip()
    value = re.split(r"(?:并|，|,|。|\.|!|！|\s)", value, maxsplit=1)[0].strip()
    return value.strip("：:「」“”\"' ")


def _is_chinese_text(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


_CANONICAL_TEMPLATES = {
    "name": "用户当前名字是 {value}",
    "location": "用户当前所在地是 {value}",
    "preference": "用户的偏好是 {value}",
    "occupation": "用户的职业是 {value}",
}


def _canonical_memory_text(text: str, prefer_language: str = "zh") -> str:
    facts = extract_facts(text or "")
    if prefer_language == "zh" and facts:
        # 只取第一个事实做规范化（后续事实会通过去重处理）
        fact_type, value = facts[0]
        template = _CANONICAL_TEMPLATES.get(fact_type)
        if template:
            return template.format(value=value)
    return (text or "").strip()


# ------------------------------------------------------------------
# LLM 事实提取器（通用：替代正则模板，覆盖所有表述方式）
# ------------------------------------------------------------------

# 事实类别定义
# CONFLICT_FACT_TYPES: 同一类别不同值会冲突（删旧存新）
# NON_CONFLICT_TYPES: 不冲突，可共存（如建议、方案）
CONFLICT_FACT_TYPES = {"name", "location", "preference", "occupation", "equipment", "project"}
NON_CONFLICT_TYPES = {"advice", "solution", "context", "plan", "observation"}

LLM_FACT_EXTRACTION_PROMPT = """你是一个事实提取专家。从对话中提取有价值的长期记忆事实。

## 规则
1. 只提取长期有效的事实（个人信息/偏好/位置/职业/设备/计划/助手建议/方案）
2. 用中文输出
3. 对用户事实：每条控制在 30 字以内
4. 对助手事实：每条控制在 30 字以内，提取最重要的 3-5 条

## 事实类别
name/location/preference/occupation/equipment/project/advice/solution/context/plan/observation

## 输出格式
返回 JSON 对象：
{{"facts": [{{"fact": "...", "source": "user/assistant", "category": "..."}}]}}

每个事实的 fact 字段必须是一个完整的句子，不能截断。

## 示例
用户："我叫小黑，最近在昆明做地质调查，用的是 AV-001 设备"
助手："建议使用便携式 XRF 分析仪，昆明附近有多个地质观测点"
输出：
{{"facts": [
  {{"fact": "用户的名字是小黑", "source": "user", "category": "name"}},
  {{"fact": "用户最近在昆明做地质调查", "source": "user", "category": "location"}},
  {{"fact": "用户使用 AV-001 设备", "source": "user", "category": "equipment"}},
  {{"fact": "建议使用便携式 XRF 分析仪", "source": "assistant", "category": "advice"}},
  {{"fact": "昆明附近有多个地质观测点", "source": "assistant", "category": "context"}}
]}}

## 对话
{conversation}

返回 JSON（格式：{{"facts": [...]}}）："""


class LLMFactExtractor:
    """用 LLM 从完整对话中提取事实（替代正则模板，覆盖所有表述方式）。"""

    @staticmethod
    async def extract(conversation: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        从对话中提取事实列表。

        Args:
            conversation: [{"role": "user"/"assistant", "content": "..."}, ...]

        Returns:
            [{"fact": str, "source": str, "category": str}, ...]
        """
        if not conversation:
            return []

        # 构建对话文本
        lines = []
        for msg in conversation:
            role = msg.get("role", "unknown")
            content = (msg.get("content") or "").strip()
            if content:
                role_label = "用户" if role == "user" else "助手"
                lines.append(f"{role_label}：{content}")
        conversation_text = "\n".join(lines)
        if not conversation_text.strip():
            return []

        prompt = LLM_FACT_EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            from config.settings import settings
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.SF_API_KEY,
                base_url=settings.SF_BASE_URL,
            )
            model = settings.MAIN_MODEL_NAME or "Qwen/Qwen3-32B"

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=512,
            )

            raw = response.choices[0].message.content
            if not raw:
                return []

            # 解析 JSON（可能包含 markdown 代码块）
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            data = json.loads(raw)

            # 统一转换为列表
            if isinstance(data, list):
                facts = data
            elif isinstance(data, dict):
                # 可能是 {"memory": [...]} 或 {"facts": [...]} 或单个事实对象
                facts = data.get("memory", data.get("facts", []))
                if not facts and "fact" in data:
                    # 单个事实对象，转成列表
                    facts = [data]
            else:
                facts = []

            # 验证格式
            valid_facts = []
            for item in facts:
                if isinstance(item, dict) and "fact" in item and "category" in item:
                    valid_facts.append({
                        "fact": str(item["fact"]).strip(),
                        "source": item.get("source", "user"),
                        "category": item.get("category", "other"),
                    })

            logger.info(f"LLM 事实提取：从 {len(conversation)} 条对话中提取 {len(valid_facts)} 条事实")
            return valid_facts

        except JSONDecodeError as e:
            logger.warning(f"LLM 事实提取 JSON 解析失败: {e}")
            return []
        except Exception as e:
            logger.warning(f"LLM 事实提取失败: {e}")
            return []


class Mem0MemoryStrategy(MemoryStrategy):
    """
    基于 mem0 的记忆策略。

    三级记忆:
    - 短期记忆: JSON 文件存储的当前会话对话历史
    - 长期记忆: mem0 存储的用户偏好、习惯
    - 语义记忆: 从对话中自动提取的事实

    多用户隔离：每个用户拥有独立的 Chroma collection。
    """

    DEFAULT_SESSION_ID = "default_session"

    def __init__(self):
        self._repo = session_repository
        self._memory = None  # 共享的默认实例（向后兼容）
        self._user_memories: Dict[str, Any] = {}  # user_id -> Memory 实例
        self._initialized = False
        self._init_error: Optional[str] = None
        self._operation_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem0")
        self._pending_memories = defaultdict(lambda: deque(maxlen=20))
        self._chroma_path: Optional[str] = None
        self._base_config: Optional[dict] = None  # 存储基础配置模板
        # 后台精炼任务跟踪
        self._refining_tasks: Dict[str, asyncio.Task] = {}  # user_id -> asyncio.Task

    def _call_mem0_locked(self, func, *args, **kwargs):
        """Run mutating mem0/Chroma operations one at a time inside this process.

        mem0.add() can spend most of its time in model inference before it writes
        to Chroma. Holding a global lock for reads during that period makes
        search/get_all time out behind a long background write. Reads are allowed
        through; writes stay serialized to avoid SQLite/Chroma write contention.
        """
        name = getattr(func, "__name__", "")
        if name in {"add", "update", "delete", "delete_all"}:
            with self._operation_lock:
                return func(*args, **kwargs)
        return func(*args, **kwargs)

    def _call_mem0_with_timeout(self, timeout_seconds: int, func, *args, **kwargs):
        call = functools.partial(self._call_mem0_locked, func, *args, **kwargs)
        future = self._executor.submit(call)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            name = getattr(func, "__name__", repr(func))
            logger.warning(f"[mem0] operation timeout after {timeout_seconds}s: {name}")
            raise TimeoutError(f"mem0 operation timeout: {name}") from exc

    async def _call_mem0_async(self, timeout_seconds: int, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        call = functools.partial(self._call_mem0_locked, func, *args, **kwargs)
        return await asyncio.wait_for(
            loop.run_in_executor(self._executor, call),
            timeout=timeout_seconds,
        )

    def _ensure_chroma_path_writable(self, chroma_path: str):
        """Create the Chroma directory and clear read-only bits on SQLite files."""
        path = Path(chroma_path)
        path.mkdir(parents=True, exist_ok=True)

        targets = [path]
        for item in path.glob("*"):
            if not item.is_file():
                continue
            if item.suffix.lower() in {".sqlite", ".sqlite3", ".db"} or item.name.endswith(("-wal", "-shm")):
                targets.append(item)

        for target in targets:
            try:
                target.chmod(target.stat().st_mode | stat.S_IWRITE)
            except Exception as exc:
                logger.warning(f"[mem0] failed to clear read-only bit for {target}: {exc}")

        probe = path / ".write_probe"
        try:
            probe.write_text(str(time.time()), encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as exc:
            raise RuntimeError(f"mem0 Chroma path is not writable: {path} ({exc})") from exc

    def _payload_to_memory_text(payload, max_len: int = 150) -> str:
        """将 payload 转为可记忆的文本（包含用户和助手双方内容）。

        助手回答使用压缩（提取关键信息）而非截断。
        """
        if isinstance(payload, list):
            parts = []
            for msg in payload:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                if role == "user":
                    # 用户消息：取前 max_len 字，尽量在完整句子处截断
                    if len(content) > max_len:
                        truncated = content[:max_len].rstrip("，,；; ")
                        if len(truncated) < 20:
                            truncated = content[:max_len]
                        parts.append(truncated)
                    else:
                        parts.append(content)
                elif role == "assistant":
                    # 助手回答：压缩关键信息，非截断
                    compressed = Mem0MemoryStrategy._compress_assistant_reply(content)
                    if len(compressed) > max_len:
                        compressed = compressed[:max_len].rstrip("，,；; ")
                    parts.append(f"[助手] {compressed}")
            return "\n".join(parts).strip()
        return str(payload or "").strip()

    def _remember_pending_payloads(self, user_id: str, session_id: str, payloads: List[Any], memory_scope: str):
        now = time.time()
        for idx, payload in enumerate(payloads):
            text = self._payload_to_memory_text(payload)
            if not text:
                continue
            metadata = {"session_id": session_id} if memory_scope == "session" else {}
            self._pending_memories[user_id].append({
                "id": f"pending-{user_id}-{now}-{idx}",
                "memory": text,
                "metadata": metadata,
                "created_at": now,
                "updated_at": now,
                "source": "pending",
            })

    def _forget_pending_payload(self, user_id: str, session_id: str, payload: Any, memory_scope: str):
        text = self._payload_to_memory_text(payload)
        if not text:
            return
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        retained = deque(maxlen=20)
        for mem in self._pending_memories.get(user_id, []):
            meta = mem.get("metadata") or {}
            if memory_scope == "session" and meta.get("session_id") != target_session_id:
                retained.append(mem)
                continue
            if mem.get("memory") != text:
                retained.append(mem)
        self._pending_memories[user_id] = retained

    def _get_pending_memories(self, user_id: str, session_id: str, memory_scope: str) -> List[Dict[str, Any]]:
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        now = time.time()
        fresh = deque(maxlen=20)
        for mem in self._pending_memories.get(user_id, []):
            created_at = self._parse_memory_time(mem.get("created_at", 0))
            if not created_at or now - created_at <= 120:
                fresh.append(mem)
        self._pending_memories[user_id] = fresh
        pending = list(fresh)
        if memory_scope == "session":
            pending = [
                mem for mem in pending
                if (mem.get("metadata") or {}).get("session_id") == target_session_id
            ]
        return pending[-5:]

    def _ensure_memory(self):
        """Lazy initialize mem0 Memory instance (shared default, for backward compat)."""
        if self._initialized:
            return

        self._initialized = True

        try:
            from mem0 import Memory
            from config.settings import settings

            api_key = settings.SF_API_KEY
            base_url = settings.SF_BASE_URL
            model = settings.MAIN_MODEL_NAME or "Qwen/Qwen3-8B"
            embedding_model = "BAAI/bge-m3"

            if not api_key or not base_url:
                self._init_error = "未配置 SF_API_KEY / SF_BASE_URL"
                logger.warning(f"mem0 初始化跳过: {self._init_error}")
                return

            backend_dir = Path(__file__).resolve().parent.parent.parent.parent
            chroma_path = str(backend_dir / "mem0_chroma")
            self._chroma_path = chroma_path
            self._ensure_chroma_path_writable(chroma_path)

            self._base_config = {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "api_key": api_key,
                        "openai_base_url": base_url,
                        "model": model,
                        "temperature": 0,
                    },
                },
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "api_key": api_key,
                        "openai_base_url": base_url,
                        "model": embedding_model,
                    },
                },
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "path": chroma_path,
                    },
                },
            }

            # 创建共享默认实例（向后兼容）
            config = copy.deepcopy(self._base_config)
            config["vector_store"]["config"]["collection_name"] = "mem0-user-memories"
            self._memory = Memory.from_config(config)
            logger.info(f"mem0 记忆引擎初始化成功, Chroma路径: {chroma_path}")
            self._init_error = None

        except ImportError:
            self._init_error = "mem0ai 未安装，请在 conda 环境中执行: pip install mem0ai"
            logger.warning(self._init_error)
        except Exception as e:
            self._init_error = f"初始化异常: {str(e)}"
            logger.error(f"mem0 初始化失败: {str(e)}")
            self._memory = None

    def _get_user_memory(self, user_id: str):
        """
        获取或创建用户专属的 Memory 实例（独立 collection）。
        每个用户拥有物理隔离的 Chroma collection：mem0-user-{user_id}
        """
        if user_id in self._user_memories:
            return self._user_memories[user_id]

        self._ensure_memory()
        if not self._base_config:
            return self._memory  # 降级到共享实例

        try:
            from mem0 import Memory
            # 每用户独立 collection 名称
            safe_user_id = user_id.replace(" ", "_").replace(".", "_")
            collection_name = f"mem0-user-{safe_user_id}"

            config = copy.deepcopy(self._base_config)
            config["vector_store"]["config"]["collection_name"] = collection_name

            user_memory = Memory.from_config(config)
            self._user_memories[user_id] = user_memory
            logger.info(f"[多用户隔离] 为用户 {user_id} 创建独立 collection: {collection_name}")
            return user_memory
        except Exception as e:
            logger.warning(f"[多用户隔离] 为用户 {user_id} 创建 Memory 失败，降级到共享实例: {e}")
            return self._memory

    def is_available(self) -> bool:
        """检查 mem0 是否可用。"""
        self._ensure_memory()
        return self._memory is not None

    def get_status(self) -> dict:
        """获取 mem0 状态信息。"""
        self._ensure_memory()
        if self._memory:
            return {
                "available": True,
                "message": "mem0 记忆引擎已就绪（多用户独立 collection）",
                "isolation_mode": "per-user-collection",
                "active_users": len(self._user_memories),
                "chroma_path": self._chroma_path,
                "pending_memories": sum(len(v) for v in self._pending_memories.values()),
            }
        return {
            "available": False,
            "message": self._init_error or "mem0 不可用",
        }

    # ------------------------------------------------------------------
    # MemoryStrategy 接口实现
    # ------------------------------------------------------------------

    def prepare_history(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        max_turn: int = 3,
        memory_scope: str = "global",
    ) -> List[Dict[str, Any]]:
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)

        logger.info(f"[mem0] prepare_history: user={user_id}, session={session_id or 'default'}, scope={memory_scope}")

        # 1. 加载短期记忆（当前会话的完整对话历史）
        chat_history = self._load_history(user_id, session_id)

        # 2. 注入 mem0 长期记忆（通过 build_memory_context_message，带冲突消解）
        memory_inject = self.build_memory_context_message(
            user_id=user_id,
            session_id=session_id,
            user_input=user_input,
            memory_scope=memory_scope,
        )
        if memory_inject:
            system_msgs = [m for m in chat_history if m.get("role") == "system"]
            other_msgs = [m for m in chat_history if m.get("role") != "system"]
            chat_history = system_msgs + [memory_inject] + other_msgs

        chat_history.append({"role": "user", "content": user_input})

        # 3. 裁剪
        return self._truncate_history(chat_history, max_turn)

    def build_memory_context_message(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        memory_scope: str = "global",
        top_k: int = 5,
    ) -> Optional[Dict[str, str]]:
        """
        Build the mem0 context message injected before the current user turn.

        global scope reads user-wide memory. session scope only reads memory
        explicitly tagged with the current session_id.
        """
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return None

        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        filters = {"user_id": user_id}
        if memory_scope == "session":
            filters["session_id"] = target_session_id

        try:
            logger.info(f"[mem0] search filters: {filters}")
            search_result = self._call_mem0_with_timeout(
                MEM0_SEARCH_TIMEOUT_SECONDS,
                user_memory.search,
                query=user_input,
                filters=filters,
                top_k=top_k,
            )
            memories = search_result.get("results", []) if isinstance(search_result, dict) else []
            logger.info(f"[mem0] search returned {len(memories)} memories")
        except TimeoutError as e:
            logger.warning(f"mem0 search timeout: {str(e)}")
            memories = self._get_fact_memory_snapshot(user_memory, user_id, target_session_id, memory_scope)
        except Exception as e:
            logger.warning(f"mem0 search failed: {str(e)}")
            memories = self._get_fact_memory_snapshot(user_memory, user_id, target_session_id, memory_scope)

        pending_memories = self._get_pending_memories(user_id, target_session_id, memory_scope)
        if pending_memories:
            logger.info(f"[mem0] using {len(pending_memories)} pending memories")
            memories = pending_memories + memories
        if not memories:
            return None

        memories = self._deduplicate_conflicting_memories(memories)
        memories = self._prefer_latest_fact_memories(memories)
        lines = []
        seen = set()
        prefer_language = "zh" if _is_chinese_text(user_input) else "raw"
        for mem in memories:
            raw_text = (mem.get("memory") or str(mem)).strip()
            text = _canonical_memory_text(raw_text, prefer_language=prefer_language)
            if not text or text in seen:
                continue
            seen.add(text)
            lines.append(f"- {text}")

        if not lines:
            return None

        scope_label = "当前会话" if memory_scope == "session" else "全局/跨会话"
        return {
            "role": "system",
            "content": (
                f"【{scope_label}记忆】以下是回答前检索到的相关记忆。"
                "如果这些记忆与用户当前输入冲突，以用户当前输入为准：\n"
                + "\n".join(lines)
            ),
        }

    def _get_fact_memory_snapshot(self, user_memory, user_id: str, session_id: str, memory_scope: str) -> List[Dict[str, Any]]:
        """Fast fallback for critical facts when vector search is slow/unavailable."""
        try:
            result = self._call_mem0_with_timeout(
                min(3, MEM0_LIST_TIMEOUT_SECONDS),
                user_memory.get_all,
                filters={"user_id": user_id},
                top_k=50,
            )
            memories = result.get("results", []) if isinstance(result, dict) else []
            if memory_scope == "session":
                memories = [
                    mem for mem in memories
                    if (mem.get("metadata") or {}).get("session_id") == session_id
                ]
            return [mem for mem in memories if extract_facts(mem.get("memory", ""))]
        except Exception as exc:
            logger.warning(f"[mem0] fact snapshot fallback failed: {exc}")
            return []

    async def save_history(
        self,
        user_id: str,
        session_id: str,
        chat_history: List[Dict[str, Any]],
        memory_scope: str = "global",
    ):
        if chat_history is None:
            return

        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID

        # 1. 保存会话历史到 JSON 文件（短期记忆）
        try:
            await self._repo.save_session(user_id, target_session_id, chat_history)
        except Exception as e:
            logger.error(f"保存用户 {user_id} 会话 {session_id} 文件失败:{str(e)}")

        # 2. 全局记忆：fire-and-forget 后台异步执行，不阻塞 SSE 响应
        if memory_scope == "global":
            self._ensure_memory()
            user_memory = self._get_user_memory(user_id)
            if user_memory:
                payloads = self._build_memory_write_payloads(chat_history)
                if payloads:
                    task = asyncio.create_task(
                        self._refine_or_save(user_id, target_session_id, payloads, memory_scope)
                    )
                    self._refining_tasks[user_id] = task

                    def _untrack_task(t):
                        try:
                            t.result()
                        except Exception as e:
                            logger.error(f"[mem0] 后台任务异常: {repr(e)}")
                        finally:
                            self._refining_tasks.pop(user_id, None)

                    task.add_done_callback(_untrack_task)

    async def _refine_or_save(self, user_id: str, session_id: str, payloads: List[List[Dict]], memory_scope: str):
        """
        后台异步：LLM 提炼 + 保存。
        1. 用 32B LLM 从对话中提取事实
        2. 按来源分组为最多 2 条：[用户] 摘要 + [助手] 摘要
        3. 存回 mem0（infer=False，中文）
        如果 LLM 失败，回退到正则提取 + 压缩原文。
        """
        try:
            user_memory = self._get_user_memory(user_id)
            if not user_memory:
                return

            for payload in payloads:
                # LLM 提取事实
                facts = await self._extract_facts_with_llm(payload)

                if facts:
                    # LLM 成功 → 按来源分组，最多 2 条记忆
                    await self._save_extracted_facts(
                        user_id, session_id, facts, user_memory,
                        {"session_id": session_id} if memory_scope == "session" else None,
                        memory_scope,
                    )
                else:
                    # LLM 失败 → 回退：压缩原文 + 正则提取
                    await self._fallback_native_add(
                        payload,
                        {"user_id": user_id, "metadata": {"session_id": session_id} if memory_scope == "session" else {}},
                        user_memory,
                        memory_scope,
                    )

            logger.info(f"mem0 refine_or_save done: user={user_id}, payloads={len(payloads)}")
        except Exception as e:
            logger.warning(f"mem0 refine_or_save 失败: {str(e)}")

    @staticmethod
    def _build_memory_write_payloads(chat_history: List[Dict[str, Any]]) -> List[List[Dict[str, str]]]:
        """
        从完整对话历史中提取最近一轮对话（用户+助手）。

        返回 [[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]]
        或 [[{"role": "user", "content": "..."}]]（如果只有用户消息）

        新策略：即使用户问题是查询性质的，只要助手给出了详细回答（包含
        建议/方案/知识点），就交给 LLM 提取器判断是否有值得保存的事实。
        """
        valid = [
            {"role": msg.get("role"), "content": (msg.get("content") or "").strip()}
            for msg in chat_history
            if msg.get("role") in {"user", "assistant"} and (msg.get("content") or "").strip()
        ]
        if not valid:
            return []

        # 找最后一条用户消息
        last_user_idx = None
        for idx in range(len(valid) - 1, -1, -1):
            if valid[idx]["role"] == "user":
                last_user_idx = idx
                break
        if last_user_idx is None:
            return []

        user_text = valid[last_user_idx]["content"]

        # 取用户消息 + 之后的助手回复（如果有）
        turn_messages = [{"role": "user", "content": user_text}]
        has_assistant_reply = False
        for idx in range(last_user_idx + 1, len(valid)):
            if valid[idx]["role"] == "assistant":
                turn_messages.append(valid[idx])
                has_assistant_reply = True
                break

        # 决策：是否值得保存
        # 1. 用户消息包含持久事实（名字/位置/偏好等）→ 保存
        if Mem0MemoryStrategy._should_persist_user_memory(user_text):
            return [turn_messages]

        # 2. 用户消息是纯查询，但助手给出了详细回答（长文本，包含建议/方案）
        #    → 也保存，让 LLM 从助手回答中提取 advice/solution/context
        if has_assistant_reply:
            assistant_text = turn_messages[-1]["content"]
            if Mem0MemoryStrategy._assistant_reply_has_value(assistant_text):
                return [turn_messages]

        return []

    @staticmethod
    def _assistant_reply_has_value(text: str) -> bool:
        """判断助手回答是否包含有价值的信息（建议/方案/知识点/详细路线等）。"""
        text = (text or "").strip()
        # 助手回答足够长（>50字），通常包含具体建议/方案/路线
        if len(text) >= 50:
            return True
        # 包含有价值的关键词
        value_markers = (
            "建议", "推荐", "方案", "方法", "路线", "导航", "步骤",
            "可以", "应该", "需要", "注意", "公里", "米", "分钟",
            "直行进入", "右转", "左转", "行驶", "到达",
        )
        if any(marker in text for marker in value_markers):
            return True
        return False

    @staticmethod
    def _should_persist_user_memory(text: str) -> bool:
        """Return True when the latest user turn is likely to contain durable facts."""
        text = (text or "").strip()
        if len(text) <= 3:
            return False

        low_value_patterns = (
            r"^(你好|您好|嗨|哈喽|hello|hi)[!！。,.，\s]*$",
            r"^(谢谢|多谢|好的|好|嗯|哦|ok|OK)[!！。,.，\s]*$",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in low_value_patterns):
            return False

        durable_patterns = (
            r"我叫(?!什么|啥|谁)\S+",
            r"(?:以后叫我|叫我|称呼我)(?!什么|啥|谁)\S+",
            r"(?:我(?:在|住在|来自)|用户(?:在|住在))\S+",
            r"我(?:喜欢|不喜欢|讨厌|常用|爱用|不用)\S+",
            r"我(?:是|从事|做|担任)\S+",
        )
        if any(re.search(pattern, text) for pattern in durable_patterns):
            return True

        durable_markers = (
            "我是", "我的", "我在", "我住", "我来自", "我喜欢", "我不喜欢",
            "我希望", "我需要", "我想要", "我经常", "我正在", "我从事", "我负责",
            "记住", "请记住", "名字", "偏好", "职业", "岗位",
            "喜欢", "讨厌", "常用", "默认", "项目", "公司", "团队",
            "我讨厌", "我不用", "我不爱",  # preference (negative)
        )
        if any(marker in text for marker in durable_markers):
            return True
        if any(marker in text for marker in ("改名", "改名字", "想叫", "叫做")):
            return True

        question_markers = (
            "?", "？", "什么", "谁", "哪里", "怎么", "如何", "为什么", "吗", "么",
            "能不能", "可不可以", "是否", "请问",
        )
        if any(marker in text for marker in question_markers):
            return False

        return len(text) >= 12

    async def _smart_add(self, user_id: str, session_id: str, text, memory_scope: str):
        """
        智能添加记忆（核心去重逻辑）—— LLM 提取 + 分类冲突检测。

        新流程：
        1. 用 LLM 从完整对话（用户+助手）中提取事实列表
        2. 如果 LLM 失败，回退到正则提取
        3. 对每个事实，按 category 分类处理：
           a. CONFLICT 类型（name/location/preference/occupation 等）：
              - 找冲突 → 删旧 → 存规范化中文文本
           b. NON-CONFLICT 类型（advice/solution/context 等）：
              - 直接存储，不做冲突检测
        4. 如果无事实提取：
           - 调用 mem0 native add（infer=True）
           - 无结果时 fallback 用 infer=False 存储原始文本
        """
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return

        messages = text if isinstance(text, list) else [{"role": "user", "content": str(text)}]
        metadata = {"session_id": session_id} if memory_scope == "session" else None
        add_kwargs = {"user_id": user_id}
        if metadata:
            add_kwargs["metadata"] = metadata

        # 步骤1：用 LLM 提取事实（优先）
        facts = await self._extract_facts_with_llm(messages)

        # 步骤2：如果 LLM 失败，回退到正则提取
        if not facts:
            # 分别处理用户和助手消息
            for msg in messages:
                msg_role = msg.get("role", "unknown")
                msg_content = (msg.get("content") or "").strip()
                if not msg_content:
                    continue
                regex_facts = extract_facts(msg_content)
                for ft, fv in regex_facts:
                    if msg_role == "assistant":
                        facts.append({
                            "fact": f"助手{_get_fact_type_label(ft)}建议/提到 {fv}",
                            "source": "assistant",
                            "category": ft,
                        })
                    else:
                        facts.append({
                            "fact": f"用户的{_get_fact_type_label(ft)}是 {fv}",
                            "source": "user",
                            "category": ft,
                        })

        # 步骤3：处理提取的事实
        if facts:
            await self._save_extracted_facts(
                user_id, session_id, facts, user_memory, metadata, memory_scope
            )
            return

        # 步骤4：无事实提取 → mem0 native add
        await self._fallback_native_add(messages, add_kwargs, user_memory, memory_scope)

    async def _extract_facts_with_llm(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """用 LLM 从对话中提取事实。"""
        return await LLMFactExtractor.extract(messages)

    async def _save_extracted_facts(
        self, user_id: str, session_id: str, facts: List[Dict[str, str]],
        user_memory, metadata: Optional[dict], memory_scope: str,
    ):
        """
        保存提取的事实 — 每组对话合并为 1 条记忆：
        用户：... | 助手：...
        """
        # 按来源分组
        user_facts = [f for f in facts if f.get("source") == "user"]
        assistant_facts = [f for f in facts if f.get("source") == "assistant"]
        logger.info(f"_save_extracted_facts: user_facts={len(user_facts)}, assistant_facts={len(assistant_facts)}")

        # 处理 CONFLICT 类型：同一类别不同值 → 删旧
        conflict_count = 0
        for fact_item in facts:
            category = fact_item.get("category", "other")
            if category in CONFLICT_FACT_TYPES:
                for conflict_id in self._find_conflicts(
                    user_id, category, fact_item["fact"]
                ):
                    try:
                        await self._call_mem0_async(
                            MEM0_ADD_TIMEOUT_SECONDS,
                            user_memory.delete,
                            conflict_id,
                        )
                        conflict_count += 1
                    except Exception:
                        pass
        logger.info(f"_save_extracted_facts: deleted {conflict_count} conflicting memories")

        # 合并为一条对话记忆
        parts = []
        if user_facts:
            user_summary = "；".join(f["fact"] for f in user_facts)
            parts.append(f"用户：{user_summary}")
        if assistant_facts:
            # 限制助手事实数量（最多8条）
            if len(assistant_facts) > 8:
                assistant_facts = assistant_facts[:8]
            assistant_summary = "；".join(f["fact"] for f in assistant_facts)
            parts.append(f"助手：{assistant_summary}")

        if not parts:
            logger.warning(f"_save_extracted_facts: no parts to save")
            return

        combined_text = " | ".join(parts)
        logger.info(f"_save_extracted_facts: combined_text={combined_text[:200]}")
        max_len = 600
        if len(combined_text) > max_len:
            cutoff = combined_text.rfind("；", 0, max_len)
            if cutoff > max_len // 2:
                combined_text = combined_text[:cutoff]
            else:
                combined_text = combined_text[:max_len]

        categories = set(f.get("category", "other") for f in facts)
        mem_meta = dict(metadata or {})
        mem_meta.update({
            "memory_kind": "conversation",
            "fact_category": ",".join(categories),
        })

        await self._call_mem0_async(
            MEM0_ADD_TIMEOUT_SECONDS,
            user_memory.add,
            [{"role": "user", "content": combined_text}],
            user_id=user_id,
            metadata=mem_meta,
            infer=False,
        )

        logger.info(f"mem0 facts saved: 1 conversation memory from {len(facts)} facts, scope={memory_scope}")

    async def _fallback_native_add(self, messages, add_kwargs, user_memory, memory_scope):
        """
        无事实提取时的回退路径 — 最多保存 2 条记忆：
        - [用户] 用户消息摘要（1条）
        - [助手] 助手回答摘要（1条）
        """
        user_parts = []
        assistant_parts = []

        for msg in messages:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            # 先尝试用正则提取结构化事实（优先级更高）
            regex_facts = extract_facts(content)
            if regex_facts:
                # 有结构化事实 → 走 _save_extracted_facts 路径
                facts_to_save = []
                for ft, fv in regex_facts:
                    source_label = "助手" if role == "assistant" else "用户"
                    facts_to_save.append({
                        "fact": f"{source_label}{_get_fact_type_label(ft)}建议/提到 {fv}",
                        "source": "assistant" if role == "assistant" else "user",
                        "category": ft,
                    })
                await self._save_extracted_facts(
                    add_kwargs["user_id"],
                    add_kwargs.get("metadata", {}).get("session_id", ""),
                    facts_to_save,
                    user_memory,
                    add_kwargs.get("metadata"),
                    memory_scope,
                )
                return

            # 无结构化事实 → 收集原文摘要（压缩而非截断）
            if role == "assistant":
                summary = Mem0MemoryStrategy._compress_assistant_reply(content)
                if len(summary) > 150:
                    summary = summary[:150].rstrip("，,；; ")
            else:
                # 用户消息：保留前 150 字
                if len(content) > 150:
                    summary = content[:150].rstrip("，,；; ")
                else:
                    summary = content

            if role == "user":
                user_parts.append(summary)
            else:
                assistant_parts.append(summary)

        # 用户消息 → 1条
        if user_parts:
            text = "[用户] " + "；".join(user_parts)
            meta = dict(add_kwargs.get("metadata", {}))
            meta.update({"memory_kind": "episodic", "fact_source": "user"})
            await self._call_mem0_async(
                MEM0_ADD_TIMEOUT_SECONDS,
                user_memory.add,
                [{"role": "user", "content": text}],
                user_id=add_kwargs["user_id"],
                metadata=meta,
                infer=False,
            )

        # 助手回答 → 1条
        if assistant_parts:
            text = "[助手] " + "；".join(assistant_parts)
            meta = dict(add_kwargs.get("metadata", {}))
            meta.update({"memory_kind": "episodic", "fact_source": "assistant"})
            await self._call_mem0_async(
                MEM0_ADD_TIMEOUT_SECONDS,
                user_memory.add,
                [{"role": "user", "content": text}],
                user_id=add_kwargs["user_id"],
                metadata=meta,
                infer=False,
            )

    def _get_fact_type_label(self, fact_type: str) -> str:
        """将事实类型映射为中文标签（用于正则回退时构建记忆文本）。"""
        labels = {
            "name": "名字",
            "location": "位置",
            "preference": "偏好",
            "occupation": "职业",
        }
        return labels.get(fact_type, fact_type)

    @staticmethod
    def _compress_assistant_reply(text: str) -> str:
        """
        将助手回答压缩为关键信息摘要（非截断）。

        策略：
        1. 移除问候语/免责声明/重复确认
        2. 提取包含关键信息的句子（路线/设备/建议/安全提示）
        3. 对超长回答，优先保留含关键词的句子
        4. 最终不超过 150 字，但保留完整语义
        """
        text = (text or "").strip()
        if not text:
            return ""
        if len(text) <= 100:
            return text

        # 步骤1：移除常见无效前缀
        skip_prefixes = [
            "你好", "您好", "好的", "没问题", "收到", "很高兴",
            "我目前无法", "目前我无法", "当前我无法",
            "基于现有信息", "根据您提供的信息", "根据您的需求",
            "作为地质野外作业助手", "以下是", "好的，",
        ]
        cleaned = text
        for prefix in skip_prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].lstrip("，。 ,：:")
                break

        # 步骤2：分句（中文句子分隔符）
        sentences = re.split(r'[。！？；\n]+', cleaned)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return cleaned[:150].strip()

        # 步骤3：给每个句子打分，优先保留含关键信息的句子
        key_indicators = [
            "建议", "推荐", "应该", "需要", "可以", "必须",
            "路线", "导航", "行驶", "右转", "左转", "到达", "公里", "米",
            "设备", "仪器", "工具", "型号", "使用",
            "注意", "安全", "危险", "防护", "应急",
            "岩石", "矿物", "地层", "采样", "勘察", "鉴定",
            "温度", "天气", "降雨", "海拔", "气候",
            "步骤", "方法", "方案", "流程",
            "直行进入", "前方", "约", "分钟", "小时",
        ]

        scored = []
        for i, sent in enumerate(sentences):
            score = 0
            for kw in key_indicators:
                if kw in sent:
                    score += 1
            # 优先保留前两句（通常是核心回答）
            if i < 2:
                score += 2
            scored.append((score, sent))

        # 步骤4：按分数排序，选最重要的，但保持原始顺序
        scored.sort(key=lambda x: -x[0])

        # 选 top 句子，总长度不超过 150 字
        selected = []
        total_len = 0
        # 先选高分句子
        for score, sent in scored:
            if score <= 0 and len(selected) >= 2:
                break
            if total_len + len(sent) + 1 > 150:
                # 截断这个句子
                remaining = 150 - total_len - 1
                if remaining > 10:
                    selected.append(sent[:remaining])
                break
            selected.append(sent)
            total_len += len(sent) + 1

        # 按原始顺序重新排列
        original_order = []
        selected_set = set(selected)
        for _, sent in scored:
            if sent in selected_set:
                original_order.append(sent)
                selected_set.discard(sent)

        compressed = "；".join(original_order) if original_order else cleaned[:150].strip()

        # 如果压缩后仍然太长，截断到最后一个完整句子
        if len(compressed) > 150:
            compressed = compressed[:150].rstrip("，,；;")

        return compressed

    @staticmethod
    def _summarize_assistant_reply(text: str) -> str:
        """
        将助手回答摘要化为有意义的记忆句（不存原始全文）。

        策略：
        1. 调用 _compress_assistant_reply 做内容压缩
        2. 添加主题标签说明是什么类型的回答
        """
        text = (text or "").strip()
        if not text:
            return ""

        # 先压缩内容
        core = Mem0MemoryStrategy._compress_assistant_reply(text)

        # 主题标签检测
        topic_labels = []
        topic_keywords = {
            "地质知识": ("岩石", "矿物", "地层", "地质", "采样", "勘察", "鉴定"),
            "设备建议": ("设备", "仪器", "工具", "推荐", "型号"),
            "路线导航": ("路线", "导航", "行驶", "公里", "右转", "左转", "到达"),
            "野外安全": ("安全", "注意", "危险", "防护", "应急"),
            "天气环境": ("天气", "温度", "降雨", "海拔", "气候"),
        }
        for topic_label, keywords in topic_keywords.items():
            if any(kw in text for kw in keywords):
                topic_labels.append(topic_label)

        topic_tag = "+".join(topic_labels) if topic_labels else "回答"

        return f"[{topic_tag}] {core}"

    def _find_conflicts(self, user_id: str, fact_type: str, fact_value: str) -> List[str]:
        """
        查找与指定事实冲突的已有记忆。

        支持两种记忆格式：
        1. LLM 提取的新格式：通过 metadata.fact_category 匹配
        2. 正则提取的旧格式：通过 extract_facts 匹配

        例如：fact_type="name", fact_value="小黑"
        会找到所有关于用户名字的记忆，返回那些名字不等于"小黑"的记忆 ID。
        """
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return []

        conflict_ids = []
        try:
            all_memories = self.get_all_memories(user_id, top_k=500)

            for mem in all_memories:
                mem_text = mem.get("memory", "")
                mem_metadata = mem.get("metadata", {}) or {}
                mem_category = mem_metadata.get("fact_category") or mem_metadata.get("fact_type", "")

                # 方式1：LLM 新格式 — 通过 metadata.category 匹配
                if mem_category:
                    if mem_category == fact_type:
                        # 同一类别，文本不同 → 冲突
                        if mem_text != fact_value and fact_value not in mem_text:
                            conflict_ids.append(mem.get("id", ""))
                    continue

                # 方式2：正则旧格式 — 通过 extract_facts 匹配
                mem_facts = extract_facts(mem_text)
                for mf_type, mf_value in mem_facts:
                    if mf_type == fact_type and mf_value != fact_value:
                        # 同一事实类型，不同值 → 冲突
                        conflict_ids.append(mem.get("id", ""))

        except Exception as e:
            logger.warning(f"[mem0] 冲突检测失败: {str(e)}")

        return conflict_ids

    async def _dedup_existing_memories(self, user_id: str):
        """
        扫描用户所有记忆，用语义相似度 + 结构化事实检测重复和冲突。

        在后台异步执行，不阻塞正常请求。
        """
        try:
            user_memory = self._get_user_memory(user_id)
            if not user_memory:
                return

            all_memories = self.get_all_memories(user_id, top_k=500)
            if len(all_memories) < 2:
                return

            ids_to_delete = set()

            # --- 策略1：语义去重 ---
            for mem in all_memories:
                mem_id = mem.get("id", "")
                mem_text = mem.get("memory", "")
                if mem_id in ids_to_delete:
                    continue

                result = user_memory.search(
                    query=mem_text,
                    filters={"user_id": user_id},
                    top_k=5,
                )
                similar = result.get("results", []) if isinstance(result, dict) else []

                for other in similar:
                    other_id = other.get("id", "")
                    if other_id == mem_id or other_id in ids_to_delete:
                        continue
                    score = other.get("score", 0)
                    if score > 0.92:
                        ids_to_delete.add(other_id)

            # --- 策略2：结构化事实冲突检测 ---
            # 提取所有记忆中的事实，按类型和值分组
            fact_groups: Dict[str, Dict[str, list]] = {}  # fact_type -> {value -> [memories]}
            for mem in all_memories:
                mem_text = mem.get("memory", "")
                facts = extract_facts(mem_text)
                for fact_type, fact_value in facts:
                    if fact_type not in fact_groups:
                        fact_groups[fact_type] = {}
                    if fact_value not in fact_groups[fact_type]:
                        fact_groups[fact_type][fact_value] = []
                    fact_groups[fact_type][fact_value].append(mem)

            # 对每个有多个不同值的事实类型，保留最新的
            for fact_type, value_map in fact_groups.items():
                if len(value_map) > 1:
                    all_values = []
                    for value, mems in value_map.items():
                        for m in mems:
                            all_values.append((value, m))

                    # 按 updated_at 排序，保留最新的
                    all_values.sort(
                        key=lambda x: self._parse_memory_time(x[1].get("updated_at", x[1].get("created_at", 0))),
                        reverse=True
                    )
                    latest_value, _ = all_values[0]

                    # 标记其他值为删除
                    for value, mem in all_values[1:]:
                        if value != latest_value:
                            mid = mem.get("id", "")
                            if mid not in ids_to_delete:
                                ids_to_delete.add(mid)

            if not ids_to_delete:
                return

            deleted = 0
            for mem_id in ids_to_delete:
                try:
                    user_memory.delete(mem_id)
                    deleted += 1
                except Exception:
                    pass

            if deleted > 0:
                logger.info(f"mem0 自动去重: 用户 {user_id} 合并了 {deleted} 条重复/冲突记忆")
        except Exception as e:
            logger.warning(f"mem0 后台去重失败: {str(e)}")

    def _add_memories_sync(self, user_id: str, session_id: str, texts: List[str], memory_scope: str = "global"):
        """同步添加记忆（回退路径，当 async event loop 不可用时调用）。包含压缩/摘要。"""
        try:
            user_memory = self._get_user_memory(user_id)
            if not user_memory:
                logger.warning(f"[mem0] 同步保存跳过: 用户 {user_id} 的 Memory 不可用")
                return
            logger.info(f"[mem0] 同步保存: user={user_id}, session={session_id}, scope={memory_scope}, 文本数={len(texts)}")
            for text in texts:
                messages = text if isinstance(text, list) else [{"role": "user", "content": str(text)}]

                # 压缩/摘要：对用户和助手消息分别处理
                compressed_messages = []
                for msg in messages:
                    role = msg.get("role")
                    content = (msg.get("content") or "").strip()
                    if not content:
                        continue

                    if role == "assistant":
                        # 助手回答：压缩关键信息
                        compressed = self._compress_assistant_reply(content)
                        compressed_messages.append({"role": "user", "content": f"[助手] {compressed}"})
                    else:
                        # 用户消息：先尝试正则提取事实
                        regex_facts = extract_facts(content)
                        if regex_facts:
                            # 有结构化事实 → 规范化
                            for ft, fv in regex_facts:
                                labels = {"name": "名字", "location": "位置", "preference": "偏好", "occupation": "职业"}
                                label = labels.get(ft, ft)
                                compressed_messages.append({"role": "user", "content": f"[用户] 用户的{label}是 {fv}"})
                        else:
                            # 无结构化事实 → 保留原文（截断到完整句子）
                            if len(content) > 150:
                                truncated = content[:150].rstrip("，,；; ")
                                if len(truncated) < 20:
                                    truncated = content[:150]
                            else:
                                truncated = content
                            compressed_messages.append({"role": "user", "content": truncated})

                if compressed_messages:
                    metadata = {"session_id": session_id} if memory_scope == "session" else None
                    add_kwargs = {"user_id": user_id}
                    if metadata:
                        add_kwargs["metadata"] = metadata
                    # 关键：infer=False 防止 mem0 把中文重写为英文
                    add_kwargs["infer"] = False
                    self._call_mem0_with_timeout(
                        MEM0_ADD_TIMEOUT_SECONDS,
                        user_memory.add,
                        compressed_messages,
                        **add_kwargs,
                    )
                    self._forget_pending_payload(user_id, session_id, text, memory_scope)
            logger.info(f"mem0 sync add (compressed): user={user_id}, count={len(texts)}, scope={memory_scope}")
        except Exception as e:
            logger.warning(f"mem0 同步添加记忆失败: {str(e)}")

    def is_refining(self, user_id: str) -> bool:
        """Check if there's an active memory refinement task for this user."""
        task = self._refining_tasks.get(user_id)
        if task is None:
            return False
        # Check if the task is still running (not done)
        return not task.done()

    async def _add_memories_background(self, user_id: str, session_id: str, texts: List[str], memory_scope: str = "global"):
        """在后台异步添加记忆，不阻塞 SSE 响应流。包含冲突检测。"""
        try:
            user_memory = self._get_user_memory(user_id)
            if not user_memory:
                logger.warning(f"[mem0] 后台保存跳过: 用户 {user_id} 的 Memory 不可用")
                return
            logger.info(f"[mem0] 后台保存: user={user_id}, session={session_id}, scope={memory_scope}, 文本数={len(texts)}")
            for text in texts:
                metadata = {"session_id": session_id} if memory_scope == "session" else None
                add_kwargs = {"user_id": user_id}
                if metadata:
                    add_kwargs["metadata"] = metadata
                messages = text if isinstance(text, list) else [{"role": "user", "content": str(text)}]
                await self._call_mem0_async(
                    MEM0_ADD_TIMEOUT_SECONDS,
                    user_memory.add,
                    messages,
                    **add_kwargs,
                )
                self._forget_pending_payload(user_id, session_id, text, memory_scope)
            logger.info(f"mem0 background native add/merge: user={user_id}, count={len(texts)}, scope={memory_scope}")
        except Exception as e:
            logger.warning(f"mem0 后台添加记忆失败: {str(e)}")

    def delete_session(self, user_id: str, session_id: str) -> bool:
        try:
            return self._repo.delete_session(user_id, session_id)
        except Exception as e:
            logger.error("删除用户 %s 会话 %s 失败: %s", user_id, session_id, str(e))
            return False

    def get_all_sessions_memory(self, user_id: str) -> List[Dict[str, Any]]:
        raw_sessions = self._repo.get_all_sessions_metadata(user_id)
        formatted_sessions = []

        for sid, create_time, data_or_error in raw_sessions:
            session_item = {"session_id": sid, "create_time": create_time}

            if isinstance(data_or_error, Exception):
                logger.error("读取会话 %s 失败: %s", sid, str(data_or_error))
                session_item.update({
                    "memory": [],
                    "total_messages": 0,
                    "error": "无法读取会话数据",
                })
            else:
                memory = data_or_error
                user_visible_memory = [
                    msg for msg in memory if msg.get("role") != "system"
                ]
                session_item.update({
                    "memory": user_visible_memory,
                    "total_messages": len(user_visible_memory),
                })

            formatted_sessions.append(session_item)

        formatted_sessions.sort(
            key=lambda x: x.get("create_time") or "",
            reverse=True,
        )
        return formatted_sessions

    async def promote_session_to_global(
        self,
        user_id: str,
        session_id: str,
        include_assistant: bool = True,
        max_messages: int = 20,
    ) -> Dict[str, Any]:
        """Promote a selected session transcript into global mem0 memory."""
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        history = self._repo.load_session(user_id, target_session_id) or []
        allowed_roles = {"user", "assistant"} if include_assistant else {"user"}
        messages = [
            {"role": msg.get("role"), "content": (msg.get("content") or "").strip()}
            for msg in history
            if msg.get("role") in allowed_roles and (msg.get("content") or "").strip()
        ][-max_messages:]

        if not messages:
            return {"promoted": 0, "message_count": 0}

        self._ensure_memory()
        if not self._get_user_memory(user_id):
            return {"promoted": 0, "message_count": len(messages), "error": "mem0 unavailable"}

        await self._smart_add(user_id, target_session_id, messages, memory_scope="global")
        return {"promoted": 1, "message_count": len(messages)}

    # ------------------------------------------------------------------
    # 记忆管理 API（Phase 2 优化）
    # ------------------------------------------------------------------

    def get_all_memories(self, user_id: str, session_id: str = None, top_k: int = 100) -> List[Dict[str, Any]]:
        """
        获取用户的记忆条目。
        如果传了 session_id，只返回该会话的记忆。

        Returns:
            [{"id", "memory", "created_at", "updated_at", "hash", "scope_label", ...}]
        """
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            logger.warning(f"mem0 不可用（用户 {user_id}），无法获取记忆列表")
            return []
        try:
            result = self._call_mem0_with_timeout(
                MEM0_LIST_TIMEOUT_SECONDS,
                user_memory.get_all,
                filters={"user_id": user_id},
                top_k=top_k,
            )
            memories = result.get("results", []) if isinstance(result, dict) else []
            if session_id:
                memories = [m for m in memories if (m.get("metadata") or {}).get("session_id") == session_id]
            pending = list(self._pending_memories.get(user_id, []))
            if session_id:
                pending = [m for m in pending if (m.get("metadata") or {}).get("session_id") == session_id]
            memories = pending + memories
            memories = self._deduplicate_conflicting_memories(memories)
            memories = self._prefer_latest_fact_memories(memories)
            for mem in memories:
                raw_text = mem.get("memory", "")
                meta = mem.get("metadata", {}) or {}

                # 对于对话精炼记忆，跳过规范化（保持原文完整）
                if meta.get("memory_kind") == "conversation":
                    mem["scope_label"] = "global" if not meta.get("session_id") else "session"
                    if meta.get("session_id"):
                        mem["session_label"] = meta["session_id"]
                    mem["fact_category"] = meta.get("fact_category", "")
                    mem.update(self._compute_memory_scores(mem))
                    continue

                # 旧格式记忆：做规范化处理
                localized_text = _canonical_memory_text(raw_text, prefer_language="zh")
                if localized_text and localized_text != raw_text:
                    mem["raw_memory"] = raw_text
                    mem["memory"] = localized_text
                if meta.get("session_id"):
                    mem["scope_label"] = "session"
                    mem["session_label"] = meta["session_id"]
                else:
                    mem["scope_label"] = "global"
                # 新增：来源和类别信息
                if meta.get("fact_source"):
                    mem["fact_source"] = meta["fact_source"]
                else:
                    mem["fact_source"] = "user"  # 默认用户
                if meta.get("fact_category"):
                    mem["fact_category"] = meta["fact_category"]
                mem.update(self._compute_memory_scores(mem))
            return memories
        except Exception as e:
            logger.error(f"mem0 获取记忆列表失败: {str(e)}")
            return []

    def get_memory(self, memory_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """获取单条记忆详情。"""
        self._ensure_memory()
        memory_store = self._get_user_memory(user_id) if user_id else self._memory
        if not memory_store:
            return None
        try:
            return self._call_mem0_with_timeout(MEM0_LIST_TIMEOUT_SECONDS, memory_store.get, memory_id)
        except Exception as e:
            logger.error(f"mem0 获取记忆 {memory_id} 失败: {str(e)}")
            return None

    def update_memory(self, user_id: str, memory_id: str, new_text: str) -> bool:
        """更新单条记忆的内容。"""
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return False
        try:
            self._call_mem0_with_timeout(MEM0_ADD_TIMEOUT_SECONDS, user_memory.update, memory_id, new_text)
            logger.info(f"mem0 更新记忆 {memory_id[:8]}... (user={user_id})")
            return True
        except Exception as e:
            logger.error(f"mem0 更新记忆失败: {str(e)}")
            return False

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除单条记忆。"""
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return False
        try:
            self._call_mem0_with_timeout(MEM0_ADD_TIMEOUT_SECONDS, user_memory.delete, memory_id)
            logger.info(f"mem0 删除记忆 {memory_id[:8]}... (user={user_id})")
            return True
        except Exception as e:
            logger.error(f"mem0 删除记忆失败: {str(e)}")
            return False

    def delete_all_memories(self, user_id: str, session_id: str = None) -> int:
        """
        删除用户的记忆。
        由于使用 per-user collection，直接调用 delete_all() 即可清空该用户的所有记忆。
        返回被删除的数量。
        """
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return 0
        try:
            existing = self.get_all_memories(user_id, session_id=session_id)
            count = len(existing)
            if count == 0:
                return 0
            if session_id:
                for mem in existing:
                    try:
                        self._call_mem0_with_timeout(MEM0_ADD_TIMEOUT_SECONDS, user_memory.delete, mem.get("id", ""))
                    except Exception:
                        pass
                logger.info(f"mem0 删除用户 {user_id} 会话 {session_id} 的 {count} 条记忆")
            else:
                self._call_mem0_with_timeout(MEM0_ADD_TIMEOUT_SECONDS, user_memory.delete_all, user_id=user_id)
                logger.info(f"mem0 清空用户 {user_id} 的 {count} 条记忆 (per-user collection)")
            return count
        except Exception as e:
            logger.error(f"mem0 清空记忆失败: {str(e)}")
            return 0

    def cleanup_expired_memories(
        self,
        user_id: str,
        max_age_days: int = 90,
        max_count: int = 200,
    ) -> Dict[str, Any]:
        """
        清理过期记忆。
        """
        self._ensure_memory()
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return {"deleted_count": 0, "remaining_count": 0, "details": []}

        try:
            import time
            all_memories = self.get_all_memories(user_id, top_k=1000)
            if not all_memories:
                return {"deleted_count": 0, "remaining_count": 0, "details": []}

            cutoff_ts = time.time() - (max_age_days * 86400)
            ids_to_delete = []
            details = []

            for mem in all_memories:
                created_at = self._parse_memory_time(mem.get("created_at", 0))
                memory_id = mem.get("id", "")
                memory_text = mem.get("memory", "")[:50]

                if created_at and created_at < cutoff_ts:
                    ids_to_delete.append(memory_id)
                    details.append(f"过期: {memory_text}")

            if len(all_memories) > max_count:
                sorted_memories = sorted(
                    all_memories,
                    key=lambda x: self._parse_memory_time(x.get("created_at", 0)),
                )
                excess = len(all_memories) - max_count
                for mem in sorted_memories[:excess]:
                    mid = mem.get("id", "")
                    if mid not in ids_to_delete:
                        ids_to_delete.append(mid)
                        details.append(f"超限: {mem.get('memory', '')[:50]}")

            for mid in ids_to_delete:
                try:
                    user_memory.delete(mid)
                except Exception:
                    pass

            remaining = len(all_memories) - len(ids_to_delete)
            logger.info(
                f"mem0 清理: 用户 {user_id} 删除 {len(ids_to_delete)} 条，剩余 {remaining} 条"
            )
            return {
                "deleted_count": len(ids_to_delete),
                "remaining_count": remaining,
                "details": details[:20],
            }
        except Exception as e:
            logger.error(f"mem0 清理过期记忆失败: {str(e)}")
            return {"deleted_count": 0, "remaining_count": 0, "details": [str(e)]}

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _check_duplicate(self, user_id: str, session_id: str, new_text: str, memory_scope: str = "global") -> Optional[str]:
        """
        检查是否存在语义重复的记忆（按 scope 过滤）。

        完全依赖 mem0 的向量语义搜索能力。
        当新文本与已有记忆的语义相似度 > 0.92 时，认为是同一事实的重复表述，
        返回已有记忆 ID，交由调用方执行 update() 而非 add()。
        """
        user_memory = self._get_user_memory(user_id)
        if not user_memory:
            return None
        try:
            filters = {"user_id": user_id}
            if memory_scope == "session":
                filters["session_id"] = session_id

            result = user_memory.search(
                query=new_text,
                filters=filters,
                top_k=3,
            )
            memories = result.get("results", []) if isinstance(result, dict) else []

            for existing in memories:
                score = existing.get("score", 0)
                if score > 0.92:
                    return existing.get("id")
        except Exception as e:
            logger.warning(f"mem0 去重检查失败: {str(e)}")
        return None

    @staticmethod
    def _deduplicate_conflicting_memories(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对检索到的记忆进行冲突消解，确保发送给 LLM 时不会收到矛盾信息。

        策略：
        1. 提取每条记忆的结构化事实（中英文都支持）
        2. 对同一事实的不同值，保留最新的一条
        3. 对剩余记忆，做文本相似度去重
        """
        if len(memories) <= 1:
            return memories

        def _parse_time(mem):
            created_at = mem.get("created_at", 0)
            if isinstance(created_at, (int, float)):
                return float(created_at)
            try:
                from datetime import datetime
                val = str(created_at).replace("Z", "+00:00")
                return datetime.fromisoformat(val).timestamp()
            except Exception:
                return 0

        # 步骤1：提取所有记忆的事实
        fact_groups: Dict[str, Dict[str, list]] = {}  # fact_type -> {value -> [memories]}
        non_fact_memories = []  # 没有匹配到任何事实的记忆

        for mem in memories:
            mem_text = mem.get("memory", "")
            facts = extract_facts(mem_text)

            if facts:
                for fact_type, fact_value in facts:
                    if fact_type not in fact_groups:
                        fact_groups[fact_type] = {}
                    if fact_value not in fact_groups[fact_type]:
                        fact_groups[fact_type][fact_value] = []
                    fact_groups[fact_type][fact_value].append(mem)
            else:
                non_fact_memories.append(mem)

        # 步骤2：对每个有冲突的事实类型，保留最新的
        kept = list(non_fact_memories)
        for fact_type, value_map in fact_groups.items():
            for value, mems in value_map.items():
                if len(mems) == 1:
                    kept.append(mems[0])
                else:
                    # 同一值的多条记忆 → 保留最新的
                    latest = max(mems, key=_parse_time)
                    kept.append(latest)

        # 步骤3：对剩余记忆，做文本相似度去重
        final_kept = []
        for mem in kept:
            mem_text = mem.get("memory", "")
            is_duplicate = False
            for existing in final_kept:
                existing_text = existing.get("memory", "")
                if len(mem_text) > 5 and len(existing_text) > 5:
                    common_prefix = 0
                    for i in range(min(len(mem_text), len(existing_text), 50)):
                        if mem_text[i] == existing_text[i]:
                            common_prefix += 1
                        else:
                            break
                    if common_prefix / max(len(mem_text), len(existing_text), 1) > 0.6:
                        mem_time = _parse_time(mem)
                        existing_time = _parse_time(existing)
                        if mem_time > existing_time:
                            final_kept.remove(existing)
                            final_kept.append(mem)
                        is_duplicate = True
                        break
            if not is_duplicate:
                final_kept.append(mem)

        return final_kept if final_kept else memories

    @staticmethod
    def _prefer_latest_fact_memories(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        latest_by_type: Dict[str, Dict[str, Any]] = {}
        others: List[Dict[str, Any]] = []

        for mem in memories:
            facts = extract_facts(mem.get("memory", ""))
            if not facts:
                others.append(mem)
                continue
            for fact_type, _ in facts:
                current = latest_by_type.get(fact_type)
                current_ts = Mem0MemoryStrategy._parse_memory_time(
                    current.get("updated_at") or current.get("created_at")
                ) if current else -1
                mem_ts = Mem0MemoryStrategy._parse_memory_time(
                    mem.get("updated_at") or mem.get("created_at")
                )
                if current is None or mem_ts >= current_ts:
                    latest_by_type[fact_type] = mem

        return list(latest_by_type.values()) + others

    @staticmethod
    def _parse_memory_time(val):
        """将 mem0 返回的时间戳（ISO 字符串或数字）转为 epoch 秒 float。"""
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return float(val)
        try:
            val = val.replace("Z", "+00:00")
            from datetime import datetime
            dt = datetime.fromisoformat(val)
            return dt.timestamp()
        except Exception:
            return 0

    def _compute_memory_scores(self, mem: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算记忆的重要程度和新鲜度。

        评分体系（1-5 星制）：
        - freshness_score: 基于新鲜度（1-5，越新越高）
        - length_score: 基于文本长度的信息量（1-5）
        - importance_score: 综合评分（1-5 星）
        """
        import time

        now = time.time()
        created_at = self._parse_memory_time(mem.get("created_at", 0))
        updated_at = self._parse_memory_time(mem.get("updated_at", 0))
        last_active = max(created_at, updated_at) if updated_at else created_at

        # 新鲜度：指数衰减，半衰期 30 天
        age_seconds = now - last_active if last_active else 0
        half_life = 30 * 86400
        freshness_ratio = max(0, 0.5 ** (age_seconds / half_life)) if age_seconds > 0 else 1.0

        # 文本长度：信息量指标（0-1，100 字符以上满分）
        text_len = len(mem.get("memory", ""))
        length_ratio = min(1.0, text_len / 100)

        # 综合重要性：新鲜度 60% + 信息量 40% → 映射到 1-5 星
        importance_raw = 0.6 * freshness_ratio + 0.4 * length_ratio
        importance_score = round(1 + importance_raw * 4, 1)
        freshness_score = round(1 + freshness_ratio * 4, 1)
        length_score = round(1 + length_ratio * 4, 1)

        # 人类可读的新鲜度标签
        age_days = age_seconds / 86400
        if age_days < 0.01:
            freshness_label = "最新"
        elif age_days < 1:
            freshness_label = "今天"
        elif age_days < 7:
            freshness_label = "近一周"
        elif age_days < 30:
            freshness_label = "近一月"
        elif age_days < 90:
            freshness_label = "近三月"
        else:
            freshness_label = "较旧"

        return {
            "freshness_score": freshness_score,
            "length_score": length_score,
            "importance_score": importance_score,
            "freshness_label": freshness_label,
            "age_days": round(age_days, 1),
        }

    def _load_history(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        target_session_id = session_id if session_id else self.DEFAULT_SESSION_ID
        try:
            session_history = self._repo.load_session(user_id, target_session_id)
            if session_history is None:
                return self._init_system_msg(target_session_id)
            return session_history
        except JSONDecodeError as e:
            logger.error(f"用户 {user_id}  会话 {session_id} 文件读取失败 原因 {e}")
            return [{"role": "system", "content": "用户历史的文件读取失败"}]

    def _init_system_msg(self, session_id: str) -> List[Dict[str, Any]]:
        return [{
            "role": "system",
            "content": f"你是一个有记忆的智能体助手，请基于上下文历史会话用户问题 (会话ID {session_id})"
        }]

    def _truncate_history(
        self,
        chat_history: List[Dict[str, Any]],
        max_turn: int = 3,
    ) -> List[Dict[str, Any]]:
        valid_roles = {"system", "user", "assistant"}
        chat_history = [msg for msg in chat_history if msg.get("role") in valid_roles]

        system_msg = [msg for msg in chat_history if msg.get("role") == "system"]
        no_system_msg = [msg for msg in chat_history if msg.get("role") != "system"]
        msg_limit = max_turn * 2
        truncate_msg = no_system_msg[-msg_limit:]
        return system_msg + truncate_msg


# 全局单例
mem0_memory = Mem0MemoryStrategy()
