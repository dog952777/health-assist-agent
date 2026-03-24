# 专栏：LangGraph — 原理、工作机制与应用

> 面向：在已了解 **LangChain 基础**（Runnable、消息、工具）的前提下，理解 **有状态、可循环** 的智能体编排。  
> **LangChain 专栏**（组件与 LCEL）：[COLUMN_LANGCHAIN.md](./COLUMN_LANGCHAIN.md)。

---

## 1. LangGraph 是什么？

**一句话**：把 LLM 应用画成 **图（Graph）**：**节点**表示一步计算（调模型、跑工具、校验……），**边**表示下一步走向；全图共享一份 **状态（State）**（常见是 `messages` 列表）。

**它不是什么**：

- 不是新的「聊天模型」，不替代 `ChatOpenAI` 等。  
- 不是必须用才能做 RAG；**固定「检索一次 → 生成一次」**用 LangChain **LCEL 链**往往更简单。

**它是什么**：

- **控制流引擎**：专门管 **分支、循环、多步**，直到满足结束条件。

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
2. 理解 **一次用户输入** 为何对应 **多次** Chat API（见本项目 `docs/PHASE3_RUN_FLOW.md` §8）。  
3. 阅读官方 **Graph 入门**、**ToolNode**、**条件边**。  
4. 再学 **Checkpointer**、**interrupt**、**Subgraph**。

**官方参考**：  
[LangGraph 文档](https://langchain-ai.github.io/langgraph/)

---

## 7. 与本项目对照

| 概念 | 本项目位置 |
|------|------------|
| 预置 ReAct 图 | `src/agent.py` → `get_react_agent()` → `create_react_agent` |
| 工具列表 | `get_react_tools()` |
| 单轮封装与取最终回复 | `chat_react()`、`_final_assistant_text()` |
| 系统提示 | `src/prompts.py` → `REACT_AGENT_PROMPT` |
| 流程图与 messages 推演 | `docs/PHASE3_RUN_FLOW.md` |

---

## 8. 常见误区

1. **「用了 LangGraph 就不用 LangChain」** — 错误；节点里仍在用 LangChain 模型与工具。  
2. **「tools 数组会按顺序执行」** — 错误；由模型 **`tool_calls`** 决定调哪个、顺序如何。  
3. **「所有 RAG 都要上 LangGraph」** — 不必；**每轮固定检索**用 LCEL 更直接。

---

*专栏为学习笔记性质，具体 API 以当前安装的 `langgraph` 版本与官方文档为准。*
