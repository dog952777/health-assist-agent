# 专栏：LangChain — 原理、工作机制与应用

> 面向：需要**系统理解** LangChain 家族（尤其 `langchain-core` + 各集成包）的学习笔记型文档。  
> 与 **LangGraph 专栏** 对照阅读：[COLUMN_LANGGRAPH.md](./COLUMN_LANGGRAPH.md)。

---

## 1. LangChain 是什么？

**一句话**：围绕大语言模型（LLM）的 **组件库 + 编排方式**，把「提示词、模型调用、检索、工具、解析」等拆成 **可替换的模块**，并用统一接口 **组合成流水线**。

**注意**：日常说的「LangChain」常指**整个生态**，而不是单一 pip 包：

| 包名 | 角色 |
|------|------|
| **`langchain-core`** | 稳定抽象：`Runnable`、`BaseMessage`、`ChatPromptTemplate`、`BaseTool`、`BaseRetriever` 等；**其它 `langchain*` 几乎都依赖它** |
| **`langchain-openai`** | **`ChatOpenAI`**、OpenAI 兼容 Embeddings 等（可配 `base_url` 走百炼等网关） |
| **`langchain-community`** | 社区 Loader、部分向量库与工具集成 |
| **`langchain`** | 高层封装与部分便捷 API（随版本变化；核心抽象仍在 core） |
| **`langchain-text-splitters`** | 文档切分为 chunk，供嵌入与检索 |
| **`langchain-chroma`** | Chroma 的 LangChain 集成（Retriever / VectorStore 等） |
| **`chromadb`** | Chroma 向量库本体（本地持久化、相似检索） |
| **`langgraph`** | **有状态图**、预置 **ReAct Agent**（如 `create_react_agent`）；节点里仍调用 core 的模型与工具 |
| **`langchain-mcp-adapters`** | 把 **MCP Server** 暴露的能力转成 **`BaseTool`**，与 ReAct 合并；**本项目固定 0.1.14** 以匹配 **`langchain-core` 0.3.x**（`0.2.x` 需 **core 1.x** 整栈升级） |
| **`pypdf`** | 读 PDF（入库用） |
| **`unstructured`（可选 extra）** | 更复杂的文档解析，按需安装 |
| **`python-dotenv`** | 读取 `.env`（**非** LangChain，仅项目配置） |

**记忆**：写业务时尽量依赖 **`langchain-core` 的接口**，换模型、换向量库时动**实现类**，少动**编排逻辑**。

---

## 2. 为什么需要 LangChain？（解决什么问题）

| 痛点 | LangChain 的做法 |
|------|------------------|
| 裸调 HTTP/SDK，每次手写消息列表、重试、流式 | `ChatModel.invoke` / `stream` 等统一形态 |
| Prompt 散落在字符串里，难维护 | `ChatPromptTemplate`、变量、`MessagesPlaceholder` |
| RAG 要接：读文件、切分、嵌入、检索、拼进提示 | Loader、Splitter、Embeddings、VectorStore、Retriever 分工 |
| 多步逻辑全是 `if/else` 和胶水函数 | **LCEL**：`A \| B \| C` 管道式组合 |
| 同一逻辑要同步/异步/流式/批量 | `Runnable` 上统一的 `invoke` / `ainvoke` / `stream` / `batch` |

---

## 3. 核心工作原理

### 3.1 Runnable：万物皆可「一段可执行逻辑」

**`Runnable`** 是 LangChain 编排的基石：

- **输入** → **输出** 明确（很多 Runnable 支持 **dict 进 dict 出**，便于链式传递）。
- 标准方法：**`invoke`**、**`ainvoke`**、**`stream`**、**`batch`**。
- **组合**：用 **`|`** 把多个 Runnable 连成一条链，数据从左流到右。

**直觉**：每个环节（模板填变量、调模型、解析 JSON）都是 Runnable；整条链也是一个 Runnable。

---

### 3.2 LCEL（LangChain Expression Language）

**形式**：`step1 | step2 | step3`

**数据流**：

1. 你 `chain.invoke({"input": "你好", "history": [...]})`。
2. **`step1`** 的输出字段若与 **`step2`** 的输入对齐（或整体是下一环能吃的结构），就自动衔接。
3. 最后一环常是 **`ChatModel`**，返回 **`AIMessage`**。

**典型模式**（对应本项目阶段 2）：

```text
RunnableLambda(检索并注入 context) | ChatPromptTemplate | ChatOpenAI
```

- **Lambda**：根据 `input` 调 `retriever`，把 `context` 写进 dict。
- **Prompt**：`system` + `system(含{context})` + `history` + `human`。
- **LLM**：生成回复。

**局限**：`| ` 本质是 **有向无环的管道**；要 **while 循环、条件分支、多节点图**，交给 **LangGraph** 更合适。

---

### 3.3 消息与 Prompt

- **`SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage`**：与 OpenAI 等 Chat API 对齐。
- **`ChatPromptTemplate.from_messages`**：模板里用占位符 **`{variable}`** 和 **`MessagesPlaceholder("history")`**，运行时一次 `invoke(variables)` 得到消息列表，再交给模型。

---

### 3.4 RAG 在 LangChain 里的位置

**数据面**：`Document(page_content, metadata)` → Loader → Splitter → Embeddings → VectorStore。  
**查询面**：`VectorStore.as_retriever()` → `Retriever.invoke(query)` → 得到 `Document` 列表 → 拼进 Prompt 或交给 Tool。

**本项目**：`src/rag.py` 负责向量侧；阶段 2 在 `agent.get_rag_chat_chain()` 里用 **RunnableLambda + Prompt + LLM** 完成「检索增强生成」。

---

### 3.5 Tool（工具）

- **`@tool`** 或 **`StructuredTool`**：把 Python 函数变成带 **name、description、args_schema** 的工具。
- **用途**：给 **Agent / LangGraph** 做 function calling；也可在链里 **`llm.bind_tools`** 自行写循环（一般不推荐重复造轮子）。

LangChain **本身不强制**「必须用 Agent」；Tool 是 **可被模型调用的能力的声明**。

---

## 4. 典型应用场景

| 场景 | 常用拼法 |
|------|----------|
| **固定 RAG 问答** | Loader + Split + Embed + VectorStore；链：`检索 \| Prompt \| LLM` |
| **带历史的聊天** | `MessagesPlaceholder` + 每轮传入 `history` |
| **结构化输出** | Prompt 约束 + 解析器，或模型厂商的 `response_format` / 工具模式 |
| **简单多步流水线** | 多个 Runnable 串联，无环 |
| **流式回复** | `chain.stream(...)`，逐块处理 |

**不适合单独用 LCEL 硬扛的**：复杂 Agent 循环、人机审批、持久化状态机 → 用 **LangGraph**。

---

## 5. 与 LangGraph 的关系

- **LangChain** 提供 **零件**（模型、消息、工具、检索器）和 **直线管道**（LCEL）。
- **LangGraph** 用这些零件搭 **图**：节点里往往还是调用 `ChatModel.invoke`、执行 `Tool`。
- **关系**：**LangGraph 建立在 LangChain 生态之上**，不是替代关系；**分工**是「直线 vs 有环/分支」。

详见 [COLUMN_LANGGRAPH.md](./COLUMN_LANGGRAPH.md)。

---

## 6. 学习路径建议

1. **Runnable + `invoke`**：任意一个 `ChatPromptTemplate \| ChatOpenAI` 跑通。  
2. **变量与 `MessagesPlaceholder`**：多轮历史。  
3. **Retriever + Prompt**：最小 RAG。  
4. **`@tool`**：单独 `invoke` 工具，再接入 Agent/图。  
5. 再读 **LangGraph 专栏**，理解何时从 LCEL 迁到图。

**官方参考**（英文为主）：  
[LangChain OSS Python 概览](https://docs.langchain.com/oss/python/langchain/overview) · [Runnable 概念（旧站）](https://python.langchain.com/docs/concepts/runnables/) · [Python API 参考（可搜索）](https://reference.langchain.com/python/langchain_core/)

---

## 7. 与本项目对照（概念 → 代码文件）

| 概念 | 本项目位置 |
|------|------------|
| LCEL RAG 链 | `src/agent.py` → `get_rag_chat_chain()` |
| 纯对话链 | `get_chat_chain()` 在 `USE_RAG=false` 时 |
| Prompt | `src/prompts.py` |
| 配置与模型 | `src/config.py`、`get_llm()` |
| 向量与检索 | `src/rag.py` |
| Tool 定义 | `src/tools/` |
| ReAct 图入口 | `get_react_agent()`、`chat_react()` |
| MCP 工具加载 | `src/tools/mcp_tools.py` |
| 敏感提示（本轮注入） | `src/sensitive_hint.py` + `agent.chat` / `chat_react` |
| 历史上限 | `src/config.py` → `CHAT_HISTORY_MAX_TURNS` |

---

## 8. 在本项目中的两条用法（LCEL 链 vs ReAct 图）

| 路径 | 何时 | 组成（直觉） | 入口 |
|------|------|--------------|------|
| **LCEL 链** | `USE_REACT_AGENT=false` | **直线管道**：`RunnableLambda`（可选检索）\| `ChatPromptTemplate` \| `ChatOpenAI` | `get_chat_chain()` → `chat()` |
| **ReAct 图** | `USE_REACT_AGENT=true`（默认） | **模型 ↔ 工具循环**：`langgraph.prebuilt.create_react_agent` | `get_react_agent()` → `chat_react()` |

- **链**：一次 `invoke` 从输入走到输出（中间可有 Lambda 做 RAG）。  
- **图**：多步；模型通过 **tool_calls** 触发工具，框架执行工具后再把 **ToolMessage** 喂回模型，直到最终回复。

---

## 9. 业务入口：优先使用 `src/agent.py` 暴露的函数

日常扩展功能时，**先找下面这些**，不必从零拼 LangChain API：

| 函数 | 作用 |
|------|------|
| `get_llm()` | 返回已按 `.env` 配置好的 **`ChatOpenAI`**（换模型/网关多改 `config` 或此处） |
| `get_chat_chain()` | 非 ReAct 的**整条链**；对返回值使用 **`.invoke({...})`** |
| `get_rag_chat_chain()` | 阶段 2：每轮 **先检索再生成**（内部 `retriever.invoke`） |
| `get_react_agent()` | 阶段 3/4：**编译后的 LangGraph**，供 `chat_react` 使用 |
| `chat(chain, user_input, history)` | 跑 LCEL **一轮**，并维护 `(用户原文, 助理原文)` 历史 |
| `chat_react(agent_graph, user_input, history)` | 跑 ReAct **一轮**；`REACT_VERBOSE=true` 时 `stream` 打印调试 |
| `get_react_tools()` | 当前启用的 **工具列表**（时间、计算器、可选 `search_health_knowledge`、可选 MCP） |

**框架对象上常见的调用习惯**（与版本细节以官方为准）：

- **链 / Runnable**：`chain.invoke({"input": "...", "history": [...]})`；流式可用 **`stream`**。  
- **图**：`graph.invoke({"messages": [...]})` 或 **`graph.stream(..., stream_mode="values")`**。  
- **检索器**：`retriever.invoke(query)`。  
- **工具**：由 Agent 绑定；业务侧用 **`@tool`** 定义 Python 函数即可，由图负责调度。

---

## 10. 阶段 1～4 与 LangChain / LangGraph 一句话对照

| 阶段 | 行为 | 涉及的 LangChain 家族能力 |
|------|------|---------------------------|
| 1 | 纯对话 | `ChatPromptTemplate` + `MessagesPlaceholder` + `ChatOpenAI`，`| ` 成链 |
| 2 | 每轮固定 RAG | `RunnableLambda` 注入 `context` + 双 `system` 模板 + `ChatOpenAI`；检索来自 `langchain-chroma` / Chroma |
| 3 | 按需工具（ReAct） | **`langgraph`** `create_react_agent` + `langchain_core` 的 Tool / 消息类型 |
| 4 | 同上 + MCP 文件系统 | **`langchain-mcp-adapters`** 将 MCP 工具并入 **`get_react_tools()`** 的列表 |

---

## 11. 官方文档与 API 检索（自学用）

| 用途 | 链接 |
|------|------|
| LangChain Python 总览 | [docs.langchain.com/oss/python/langchain](https://docs.langchain.com/oss/python/langchain/overview) |
| LangGraph（图与 Agent） | [docs.langchain.com/oss/python/langgraph](https://docs.langchain.com/oss/python/langgraph/overview) |
| 按符号搜索 API | [reference.langchain.com/python](https://reference.langchain.com/python/langchain_core/)（如搜 `ChatPromptTemplate`、`Runnable`） |

---

*专栏为学习笔记性质，具体 API 以当前安装的包版本与官方文档为准。*
