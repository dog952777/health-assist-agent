# 专栏：LangGraph — 原理、工作机制与应用

> 面向：在已了解 **LangChain 基础**（Runnable、消息、工具）的前提下，理解 **有状态、可循环** 的智能体编排。  
> **LangChain 专栏**（组件与 LCEL、依赖包、业务入口）：[COLUMN_LANGCHAIN.md](./COLUMN_LANGCHAIN.md)。

---

## 1. LangGraph 是什么？

**一句话**：把 LLM 应用画成 **图（Graph）**：**节点**表示一步计算（调模型、跑工具、校验……），**边**表示下一步走向；全图共享一份 **状态（State）**（常见是 `messages` 列表）。

**它不是什么**：

- 不是新的「聊天模型」，不替代 `ChatOpenAI` 等。  
- 不是必须用才能做 RAG；**固定「检索一次 → 生成一次」**用 LangChain **LCEL 链**往往更简单。

**它是什么**：

- **控制流引擎**：专门管 **分支、循环、多步**，直到满足结束条件。

### 1.1 与本项目相关的 pip 包

| 包名 | 角色 |
|------|------|
| **`langgraph`** | 主包：**预置 Agent**（如 `create_react_agent`）、图的 **编译** 与 **`invoke` / `stream`**；自定义时再使用 `StateGraph`、`ToolNode`、条件边等 |
| **`langgraph-checkpoint`**（随依赖安装） | **检查点**：持久化图状态、断点恢复；**本项目 CLI 对话未显式配置 checkpointer**，一轮轮状态在**进程内存**中 |
| **`langgraph-sdk`**（随依赖安装） | 与 **LangGraph 平台 / 远程 API** 交互；**本地 `python -m src.main` 一般不直接写 SDK 代码** |

**记忆**：当前仓库里与 LangGraph **直接打交道**的入口主要是 **`langgraph.prebuilt.create_react_agent`**；需要人机协同、持久会话、复杂分支时再深入 **Checkpoint / interrupt / Subgraph**。

---

## 2. 为什么需要 LangGraph？（与手写循环对比）

手写 ReAct 常见模式：

```text
循环：
  调模型
  若有 tool_calls → 执行工具 → 把结果写入消息 → 继续循环
  否则 → 结束
```

**项目变大时的问题**：

- 分支增多（鉴权、重试、人工审核）→ `if/else` 难维护。  
- 状态除了 `messages` 还有 `user_id`、业务标志 → 散落全局易乱。  
- 需要 **断点续跑、调试某一步、子流程复用** → 手写成本高。

**LangGraph 的解法**：用 **显式图 + 结构化 State** 表达流程，节点保持小而纯；**编译**成可 `invoke` / `stream` 的对象。

---

## 3. 核心工作原理

### 3.1 状态（State）

- **定义**：通常为 **`TypedDict` 或 Pydantic 模型**，字段如 `messages: Annotated[list, add_messages]`。  
- **语义**：每个节点可读当前状态，并 **返回要合并的更新**（例如新增几条消息）。  
- **为什么用 `messages`**：与 Chat API、Tool Calling 天然对齐，工具结果以 **`ToolMessage`** 进列表，下一轮模型才能看见。

---

### 3.2 节点（Node）

- **本质**：函数（或 Runnable），输入来自状态，输出 **部分状态更新**。  
- **典型节点**：  
  - **`call_model`**：取 `messages` → `llm.invoke` → 返回新的 `AIMessage`。  
  - **`tools`**：根据最近 `AIMessage.tool_calls` 执行对应 Python 工具 → 返回若干 `ToolMessage`。

---

### 3.3 边（Edge）与条件路由

- **固定边**：A 执行完 **总是** 到 B。  
- **条件边**：根据 **状态或节点返回值** 选择 **去工具节点**、**回模型** 还是 **END**。

**ReAct 的关键条件**：  
「最新一条 `AIMessage` 是否包含 **`tool_calls`**？」

- **是** → 进入工具节点 → 再回模型节点。  
- **否** → 认为已得到最终自然语言答复 → **结束**。

这就是图上的 **环**（模型 ⟷ 工具）。

---

### 3.4 编译（compile）与运行

- **定义图**：注册节点、边、入口、结束条件。  
- **`compile()`** → **`CompiledGraph`**。  
- **`invoke(initial_state)`**：从入口跑到终止；内部可能 **多次** 经过模型节点。  
- **`stream`**：逐步输出中间状态，便于日志与 UI。

---

### 3.5 `create_react_agent`（预置图）

**作用**：不必从零连线，直接得到「**模型 ⟷ 工具**」的标准 ReAct 拓扑。

**参数直觉**（与本项目一致）：

- **`model`**：如 `ChatOpenAI`。  
- **`tools`**：工具列表；模型从 **schema** 里 **按名称选择**，不是按数组顺序轮流执行。  
- **`prompt`**：系统层指令（人设、何时用哪个工具），在调用模型时进入上下文。

**返回值**：编译好的图，输入 **`{"messages": [...]}`**（具体 state schema 以版本为准）。

---

## 4. 典型应用场景

| 场景 | 为何适合用图 |
|------|----------------|
| **ReAct / Tool Agent** | 天然多轮：模型 → 工具 → 模型 |
| **多分支工作流** | 检索失败走联网、成功走总结等 |
| **人机协同（HITL）** | 在某节点 **interrupt**，等人确认再继续 |
| **需要持久化会话** | **Checkpointer** 存状态，支持恢复与调试 |
| **子流程复用** | **Subgraph** 嵌套 |

---

## 5. 与 LangChain 的分工（再强调）

| 维度 | LangChain（LCEL） | LangGraph |
|------|-------------------|-----------|
| 拓扑 | 多为 **DAG 管道** `A \| B \| C` | **有环图** + 条件边 |
| 状态 | 常是「这一跳的输入输出」 | **显式全局 State**（可持久化） |
| 典型用例 | 固定 RAG、单次 transform | Agent、审批流、多步决策 |

**协作方式**：图 **节点内部** 仍大量使用 LangChain 的 **ChatModel、Tool、Message**。

---

## 6. 学习路径建议

1. 先跑通 **`invoke({"messages": [...]})`**，打印最终 **`messages` 长度与类型**（Human / AI / Tool）。  
2. 理解 **一次用户输入** 为何对应 **多次** Chat API（见本项目 [PHASE3_RUN_FLOW.md](./PHASE3_RUN_FLOW.md)）。  
3. 阅读官方 **Graph 入门**、**ToolNode**、**条件边**。  
4. 再学 **Checkpointer**、**interrupt**、**Subgraph**。

**官方参考**（与当前文档站一致）：  
[LangGraph OSS Python 概览](https://docs.langchain.com/oss/python/langgraph/overview) · [旧站文档](https://langchain-ai.github.io/langgraph/) · [Python API 参考](https://reference.langchain.com/python/langgraph/)

---

## 7. 与本项目对照（概念 → 代码文件）

| 概念 | 本项目位置 |
|------|------------|
| 预置 ReAct 图构建 | `src/agent.py` → `get_react_agent()` → `langgraph.prebuilt.create_react_agent` |
| 工具列表（并入同一张图） | `get_react_tools()`（含可选 RAG 工具、可选 MCP） |
| 单轮对话封装 | `chat_react()` |
| 执行图（含 Verbose 下 `stream` / fallback `invoke`） | `_run_react_graph()` |
| 从 `messages` 取最终对用户可见文案 | `_final_assistant_text()` |
| ReAct 调试打印（步骤摘要、完整消息链） | `_log_react_step`、`_log_full_message_chain` |
| 系统提示（含 MCP 追加段） | `src/prompts.py` → `REACT_AGENT_PROMPT`、`REACT_AGENT_MCP_HINT` |
| 入口选择链还是图 | `src/main.py`（`USE_REACT_AGENT`） |
| 流程与 messages 推演 | [PHASE3_RUN_FLOW.md](./PHASE3_RUN_FLOW.md)、[PHASE4_RUN_FLOW.md](./PHASE4_RUN_FLOW.md) |

---

## 8. 何时走 LangGraph、何时仍用 LCEL

| `USE_REACT_AGENT`（`.env`） | 编排方式 | 入口 |
|---------------------------|----------|------|
| **`true`（默认）** | **LangGraph** 预置 ReAct 图 | `main` → `get_react_agent()` → `chat_react()` |
| **`false`** | **LangChain** LCEL 链 | `get_chat_chain()` → `chat()` |

**阶段 4（MCP）**：在 **`USE_REACT_AGENT=true`** 的前提下，仅 **`USE_MCP=true`** 时把 MCP 工具 **extend 进 `get_react_tools()`**；**仍是同一张 ReAct 图**，没有单独的「MCP 子图」。

---

## 9. 业务入口：与 LangGraph 直接相关的 `src/agent.py` API

日常扩展 **Agent 行为**时，优先改下面这些，而不是假设存在另一套「LangGraph 专用业务层」：

| 符号 | 作用 |
|------|------|
| `get_react_agent()` | 用当前 `get_llm()` + `get_react_tools()` + `_react_system_prompt()` 构建并返回 **CompiledGraph** |
| `get_react_tools()` | 提供给 `create_react_agent` 的 **工具列表**（LangChain `BaseTool`） |
| `chat_react(agent_graph, user_input, history)` | 把历史与本轮用户句转成 **`messages`**，调用 `_run_react_graph`，再用 `_final_assistant_text` 得到字符串回复 |
| `_run_react_graph(agent_graph, messages)` | **`REACT_VERBOSE=false`**：直接 `agent_graph.invoke({"messages": ...})`；**为 true**：优先 **`stream(..., stream_mode="values")`** 打印每步，失败则 **fallback `invoke`** |
| `_final_assistant_text(messages)` | 从完整 **`messages`** 中倒序查找 **最后一条带正文的 `AIMessage`**，作为本轮展示给用户的内容 |

**图的输入约定**（与本项目一致）：**`{"messages": [...]}`**；其中 `messages` 为 `HumanMessage` / `AIMessage` / `ToolMessage` 等（来自 **`langchain_core.messages`**）。

---

## 10. `invoke` 与 `stream` 在本项目中的含义

- **`invoke`**：一次调用跑完**本轮用户问题**所需的 **全部** 图步（可能多轮「模型 → 工具 → 模型」），返回 **最终 state**（含完整 `messages`）。  
- **`stream(..., stream_mode="values")`**：可能在中途多次 yield **state 快照**；不同版本下「每步是否都 yield」行为可能不同，因此本项目在 **`REACT_VERBOSE=true`** 时除逐步日志外，还会在末尾打印 **完整消息链**，便于对照 **`tool_calls`** 与 **`ToolMessage`**。  
- **网络错误**：若在 `stream` 阶段失败，`main.py` 可能收到异常并提示检查代理/API；与 LangGraph 逻辑无关，属 **LLM 连接**问题。

---

## 11. 阶段 3 / 4 与 LangGraph（一句话）

| 阶段 | LangGraph 承担什么 |
|------|---------------------|
| **3** | 用 **`create_react_agent`** 搭好 **ReAct 拓扑**，按需调用 **时间 / 计算器 / 可选知识库检索工具** |
| **4** | **拓扑不变**；工具列表增加 **MCP filesystem**（经 `langchain-mcp-adapters` 转成 `BaseTool`），模型仍通过 **同一张图** 调度 |

---

## 12. 官方文档与 API 检索（自学用）

| 用途 | 链接 |
|------|------|
| LangGraph Python 总览 | [docs.langchain.com/oss/python/langgraph](https://docs.langchain.com/oss/python/langgraph/overview) |
| 与 LangChain 文档同一体系 | [docs.langchain.com](https://docs.langchain.com/) |
| 按符号搜 Python API | [reference.langchain.com/python/langgraph](https://reference.langchain.com/python/langgraph/)（如搜 `create_react_agent`、`StateGraph`） |

---

## 13. 常见误区

1. **「用了 LangGraph 就不用 LangChain」** — 错误；节点里仍在用 LangChain 的 **ChatModel、Tool、Message**。  
2. **「tools 数组会按顺序执行」** — 错误；由模型 **`tool_calls`** 决定调哪个、顺序如何。  
3. **「所有 RAG 都要上 LangGraph」** — 不必；**每轮固定检索**用 LCEL 更直接（见 `get_rag_chat_chain`）。  
4. **「MCP 会单独起一个 LangGraph」** — 在本项目中 **错误**；MCP 只是 **更多 Tool** 加入 **同一 ReAct 图**。

---

*专栏为学习笔记性质，具体 API 以当前安装的 `langgraph` 版本与官方文档为准。*
