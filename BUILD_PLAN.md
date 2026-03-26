# 健康助理智能体 — 构建计划

> 技术栈：Python + LangChain + MCP + RAG + ReAct  
> 环境：mise + Poetry

---

## 一、目标与能力范围

**目标**：搭建一个可对话的「健康助理」智能体，能：

- 回答常见健康/用药问题（基于 RAG 知识库）
- 通过 ReAct 推理并调用工具（查日历、记提醒、查天气等）
- 通过 MCP 接入外部能力（文件、日历、搜索等）
- 不替代医生，仅作信息参考与生活助理

**能力边界**：仅提供参考信息与提醒，不给出诊断或处方建议；敏感场景需提示「请咨询医生」。

---

## 二、整体架构（简化）

```
用户输入
    ↓
LangChain ReAct Agent
    ├── LLM（OpenAI / 国产大模型）
    ├── Tools
    │   ├── RAG 检索工具（医学/用药知识）
    │   └── MCP 工具（日历、备忘、文件等）
    └── 输出 → 回复用户
```

---

## 三、分阶段构建计划

### 阶段 0：环境与项目初始化（第 1 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 0.1 | 用 mise 切到目标 Python 版本（建议 3.11+） | `.mise.toml` 或 `mise.toml` |
| 0.2 | 用 Poetry 初始化项目、加基础依赖 | `pyproject.toml`、`poetry.lock` |
| 0.3 | 建目录：`src/`、`data/`、`docs/`、`tests/` | 清晰项目结构 |

**依赖建议**（Poetry）：

- `langchain`、`langchain-openai`（或 `langchain-anthropic` 等）
- `langchain-community`（可选，用于更多检索器）
- `langgraph`（用于更可控的 ReAct/多步推理）
- `langchain-mcp-adapters` 或社区版 `langchain-mcp-tools`（MCP → LangChain Tools）
- RAG：`langchain-chroma` 或 `langchain-qdrant` + 向量库客户端
- 文档加载：`unstructured`、`pypdf` 等（按知识库格式选）

---

### 阶段 1：LangChain + LLM 对话（第 2 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1.1 | 配置 API Key（环境变量 / `.env`） | 不把 key 写进代码 |
| 1.2 | 用 LangChain 接一个 LLM（如 ChatOpenAI） | 能跑通简单对话 |
| 1.3 | 加 System Prompt：角色=「健康助理」，强调不替代医生 | `src/prompts.py` 或类似 |
| 1.4 | 实现一个最简单的 CLI 或 Gradio 对话界面 | 能多轮对话 |

**验收**：用户说「你好」「今天头疼怎么办」，助手能基于 LLM 回复（此时还未接 RAG/工具）。

---

### 阶段 2：RAG — 医学/用药知识库（第 3 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 2.1 | 准备知识来源：公开医学常识、用药说明等（PDF/TXT/MD），注意版权与合规 | `data/knowledge/` 下文档 |
| 2.2 | 文档加载与切分（LangChain Document Loaders + Text Splitters） | 管道：文件 → chunks |
| 2.3 | 选一个向量库（Chroma / Qdrant / 其他），建索引 | 本地或远程向量库 |
| 2.4 | 实现「检索器」：query → 取 top-k 文档片段 | 可封装成 LangChain Retriever |
| 2.5 | 把检索器做成 **Tool**（如 `search_medical_knowledge`），供 Agent 调用 | 一个 LangChain Tool |

**验收**：问「布洛芬一天最多吃几次」，Agent 能通过该 Tool 查到知识库并回答（可先手动调 Tool 再接到 Agent）。

---

### 阶段 3：ReAct Agent + 工具（第 4 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 3.1 | 定义 2～3 个简单工具（如：当前时间、简单计算），用 LangChain 的 `@tool` 或 `StructuredTool` | 能单独测试每个 tool |
| 3.2 | 把 RAG 检索工具加入工具列表 | tools = [rag_tool, time_tool, ...] |
| 3.3 | 用 LangChain 的 ReAct 范式创建 Agent（如 `create_react_agent` + AgentExecutor） | 能根据问题选工具并执行 |
| 3.4 | 设计 ReAct 的 System Prompt：何时用 RAG、何时用其它工具、何时只对话 | 减少乱用工具 |

**验收**：用户问「我该几点吃药」或「查一下布洛芬用法」，Agent 能决定调用 RAG 或时间/日历类工具并给出合理回复。

---

### 阶段 4：接入 MCP（第 5 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 4.1 | 选 MCP 服务端：如 filesystem、memory、calendar 等（可先本地/官方示例） | 能独立跑通 MCP Server |
| 4.2 | 用 `langchain-mcp-adapters` 的 `convert_mcp_tool_to_langchain_tool` 或社区库把 MCP tools 转成 LangChain Tools | 得到 `mcp_tools` 列表 |
| 4.3 | 将 MCP 工具与现有 RAG/时间等工具合并，一起交给 ReAct Agent | 一个统一工具集 |
| 4.4 | 在 Prompt 中说明各 MCP 工具用途（读文件、记备忘等），避免误用 | 更新 System Prompt |

**验收**：用户说「把明天 8 点设为吃药提醒」或「读一下我存的用药说明」，Agent 能通过 MCP 工具执行。

---

### 阶段 5：整合、安全与体验（第 6 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 5.1 | 敏感话题检测：若涉及「诊断」「处方」「急诊」等，回复中加强「请咨询医生」 | 可在 Prompt 或后处理里做 |
| 5.2 | 对话历史：用 LangChain 的 `ChatMessageHistory` 或 LangGraph 的 checkpointer，支持多轮上下文 | 能连续对话 |
| 5.3 | 简单评估：准备 10～20 条测试问题（知识类、工具类、边界类），跑一遍并记录 | `docs/eval_examples.md` |
| 5.4 | 部署方式：CLI / Gradio / FastAPI（按需选），写清运行方式 | README 与启动命令 |

**验收**：多轮对话稳定、敏感问题有免责提示、文档齐全可复现。

**本仓库实现说明**：`src/sensitive_hint.py` + `src/agent.py`（历史截断与本轮注入）+ `docs/PHASE5_LEARNING.md` / `docs/PHASE5_RUN_FLOW.md` + `docs/eval_examples.md`。

---

## 四、推荐学习与参考顺序

1. **LangChain 基础**：LCEL、ChatPromptTemplate、MessagesPlaceholder。  
2. **RAG**：Document Loaders → Splitters → Embeddings → VectorStore → Retriever。  
3. **Tools & Agent**：`@tool`、`create_react_agent`、AgentExecutor。  
4. **MCP**：先跑通一个 MCP Server，再用 adapter 转成 LangChain Tools。  
5. **LangGraph**（可选）：用图把「检索 → 推理 → 工具」流程画清楚，便于扩展。

---

## 五、项目目录结构建议

```
AI/
├── .env.example          # 环境变量示例（不含真实 key）
├── .mise.toml            # Python 版本
├── pyproject.toml        # 依赖与脚本
├── BUILD_PLAN.md         # 本构建计划
├── README.md
├── data/
│   └── knowledge/        # 医学/用药文档（你自行准备）
├── docs/
│   └── eval_examples.md  # 测试问题与预期
├── src/
│   ├── __init__.py
│   ├── main.py           # 入口：CLI 或启动服务
│   ├── agent.py          # ReAct Agent、多轮截断
│   ├── sensitive_hint.py # 阶段 5：敏感类别与本轮注入
│   ├── prompts.py        # System / User 模板
│   ├── rag.py            # 文档加载、向量库、检索器
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── rag_tool.py   # RAG 检索 Tool
│   │   └── mcp_tools.py  # MCP 转 LangChain Tools
│   └── config.py         # 配置（模型、向量库、历史上限等）
└── tests/
    └── test_agent.py     # 简单单测
```

---

## 六、每一步你可以怎么问

- **阶段 0**：「按 BUILD_PLAN 阶段 0 帮我写 `.mise.toml` 和 `pyproject.toml`，并建好目录。」  
- **阶段 1**：「实现阶段 1：LangChain + LLM 对话，并加健康助理的 System Prompt。」  
- **阶段 2**：「实现阶段 2：RAG，用 Chroma，知识放在 `data/knowledge`。」  
- **阶段 3**：「实现阶段 3：把 RAG 做成 Tool，并搭 ReAct Agent。」  
- **阶段 4**：「实现阶段 4：接一个 MCP Server（如 filesystem），并合并到现有 Agent。」  
- **阶段 5**：「实现阶段 5：加敏感词提示、多轮历史，并写 README。」

按上述顺序一步一步做，每完成一个阶段再进入下一阶段，更容易排查问题和迭代。
