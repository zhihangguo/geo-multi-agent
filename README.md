# GeoAssist 地学野外作业智能助手

> 面向地质野外作业场景的多智能体系统，支持知识检索、实时搜索与地图导航。

---

## 核心功能

- **多智能体协作**：调度 Agent + 地质知识专家 + 野外后勤导航专家
- **知识库检索（RAG）**：查询地质知识文档（岩石鉴定、矿物分类、地层划分等）
- **实时搜索**：联网检索天气、灾害预警、实时资讯
- **地图导航**：地点查询、IP 定位、路径生成、附近补给点/医疗站查询
- **双架构可切换**：支持 `mode=agents | langgraph` 直接切换后端逻辑

---

## 系统架构

### 1. Agents SDK 架构

- 调度 Agent 负责任务拆解与工具调用
- 技术 Agent 负责知识库与搜索
- 后勤 Agent 负责地图与站点查询

### 2. LangGraph 架构

- LangGraph 负责流程编排
- LangChain Agent 负责工具调用
- 与原架构能力完全一致

---

## 快速开始

### 后端

```bash
cd backend/app
pip install -r requirements.txt
cp .env.example .env  # 编辑填入你的 API Key
python -m uvicorn api.main:app --reload
```

### 前端

```bash
cd front/agent_web_ui
npm install
npm run dev
```

---

## 架构切换

前端已提供切换按钮，后端使用 `mode` 参数切换：

```json
{
  "query": "花岗岩和闪长岩如何区分？",
  "mode": "langgraph"
}
```

- `mode=agents` → Agents SDK 架构
- `mode=langgraph` → LangGraph 架构

---

## 项目结构

```
backend/
├── app/
│   ├── api/              # API 路由
│   ├── config/           # 配置管理
│   ├── multi_agent/      # Agents SDK 架构
│   ├── multi_agent_langgraph/  # LangGraph 架构
│   └── ...
└── knowledge/            # 知识库服务

front/
├── agent_web_ui/         # 前端主界面
└── knowlege_platform_ui/ # 知识平台界面
```

---

## 许可证

MIT License
