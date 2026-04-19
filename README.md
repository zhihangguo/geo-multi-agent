# GeoAssist - 地学野外作业智能助手

> 基于多智能体协作的地质领域 AI 助手，支持知识检索、实时搜索与地图导航。提供 OpenAI Agents SDK 与 LangGraph 双架构，运行时可切换。

---

## 功能清单

- **多智能体协作**：调度 Agent + 地质知识专家 + 野外后勤导航专家，自动拆解复杂任务
- **RAG 知识库检索**：基于 Chroma 向量数据库，支持岩石鉴定、矿物识别、地层分析等专业查询
- **联网实时搜索**：通过 MCP 协议接入百炼 WebSearch，获取天气、灾害预警、实时资讯
- **地图导航服务**：地址解析、IP 定位、导航链接生成、附近补给点/医疗站查询
- **双架构运行时切换**：`mode=agents`（OpenAI Agents SDK）或 `mode=langgraph`（LangGraph StateGraph）
- **会话记忆管理**：多会话并行、轮次裁剪、文件持久化 + 原子写入
- **流式输出（SSE）**：THINKING / PROCESS / ANSWER / DEGRADE 四级事件，决策过程对前端完全透明
- **LangGraph 高级能力**：Checkpointing 断点续传、History 历史回溯、Time Travel 时间旅行、Interrupt 中断等待

---

## 系统架构

### 架构 A：OpenAI Agents SDK

- **编排机制**：Orchestrator Agent 通过 function calling 自主调用专家工具
- **专家工具**：`consult_technical_expert`（技术专家）+ `query_service_station_and_navigate`（后勤专家）
- **流式输出**：原生 `stream_events()` 支持 token 级流式

### 架构 B：LangGraph

- **编排机制**：StateGraph 显式建模 4 个节点（orchestrator → dispatcher → technical/service）
- **路由策略**：关键词兜底 + LLM structured output 混合路由
- **高级能力**：MemorySaver Checkpointing、条件边循环、节点级手动重试

两种架构对外能力完全一致，仅内部实现方式不同。

---

## 快速开始

### 环境要求

- Python 3.11+（推荐 conda 环境 `ITS_Multi_Agent`）
- Node.js 18+
- MySQL（用于站点数据查询）

### 1. 配置环境变量

```bash
# 主智能体服务
cp backend/app/.env.example backend/app/.env

# 知识库服务
cp backend/knowledge/.env.example backend/knowledge/.env
```

编辑 `.env` 文件，填入你的 API Key：
- 硅基流动 API Key（SF_API_KEY）或 阿里百炼 API Key（AL_BAILIAN_API_KEY）（至少配置一个）
- 百度地图 AK（BAIDUMAP_AK）
- MCP 联网搜索 URL（DASHSCOPE_BASE_URL）
- MySQL 连接信息

### 2. 安装依赖

```bash
# 方式一：使用根目录统一 requirements.txt
pip install -r requirements.txt

# 方式二：各子目录独立安装
cd backend/knowledge && pip install -r requirements.txt
cd backend/app && pip install -r requirements.txt
```

### 3. 启动服务（按顺序）

```bash
# 第一步：启动知识库服务（端口 8001）
cd backend/knowledge
python -m uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8001 --reload

# 第二步：启动主智能体服务（端口 8000）
cd backend/app
python -m uvicorn api.main:create_fast_api --factory --reload

# 第三步：启动前端（端口 5173）
cd front/agent_web_ui
npm install
npm run dev
```

> **注意**：知识库服务（8001）必须先启动，主智能体服务（8000）依赖它进行 RAG 检索。

### 一键启动（Windows PowerShell）

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dev-terminals.ps1
```

---

## API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/query` | POST | 多智能体对话接口，SSE 流式返回 |
| `/api/knowledge_query` | POST | 知识仓智搜专用接口，直接查询 RAG 知识库 |
| `/api/user_sessions` | POST | 获取用户历史会话列表 |
| `/api/delete_session` | POST | 删除指定会话 |
| `/api/langgraph/history` | POST | 获取 LangGraph 执行历史 |
| `/api/langgraph/replay` | POST | 从指定 checkpoint 重放执行 |
| `/api/langgraph/pause` | POST | 中断执行等待用户输入 |
| `/api/langgraph/resume` | POST | 从中断点继续执行 |

### 请求示例

```json
{
  "query": "花岗岩和闪长岩如何区分？",
  "context": {
    "user_id": "root1",
    "session_id": ""
  },
  "mode": "langgraph"
}
```

---

## 项目结构

```
├── requirements.txt          # 统一依赖列表
├── .gitignore
├── start-dev-terminals.ps1   # 一键启动脚本
│
├── backend/
│   ├── app/                  # 主智能体服务（端口 8000）
│   │   ├── api/              #   API 路由入口
│   │   ├── services/         #   业务服务层（任务处理、会话管理、流式响应）
│   │   ├── multi_agent/      #   OpenAI Agents SDK 架构
│   │   ├── multi_agent_langgraph/  # LangGraph 架构
│   │   ├── infrastructure/   #   工具层（MCP、知识库、数据库）
│   │   ├── repositories/     #   数据持久化（会话读写）
│   │   ├── schemas/          #   请求/响应模型
│   │   ├── config/           #   配置管理
│   │   └── prompts/          #   Agent Prompt 模板
│   │
│   └── knowledge/            # 知识库服务（端口 8001）
│       ├── api/              #   API 路由
│       └── services/         #   文档爬虫、数据摄取、检索服务
│
└── front/
    ├── agent_web_ui/         # 前端主界面（Vue 3，端口 5173）
    └── knowlege_platform_ui/ # 知识管理平台界面
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus |
| 后端 | FastAPI + Uvicorn |
| AI 框架 A | OpenAI Agents SDK |
| AI 框架 B | LangChain + LangGraph |
| 向量数据库 | Chroma |
| 关系数据库 | MySQL + PyMySQL + DBUtils |
| 外部服务 | MCP（百炼 WebSearch、百度地图） |
| 流式通信 | Server-Sent Events (SSE) |

---

## 注意事项

1. **API Key 安全**：请勿将 `.env` 文件提交到公开仓库。`.env` 已在 `.gitignore` 中排除
2. **知识库先行**：必须先启动知识库服务（8001），再启动主智能体服务（8000）
3. **模型选择**：推荐使用 Qwen3 系列模型（硅基流动 `Qwen/Qwen3-32B` 或 阿里百炼 `qwen3-max`）
4. **MySQL 数据**：站点查询功能依赖 MySQL 数据库，需提前导入站点数据

---

## 许可证

MIT License
