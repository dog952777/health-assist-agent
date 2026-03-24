# 专栏：LangChain — 原理、工作机制与应用

> 面向：需要**系统理解** LangChain 家族（尤其 `langchain-core` + 各集成包）的学习笔记型文档。  
> 与 **LangGraph 专栏** 对照阅读：[COLUMN_LANGGRAPH.md](./COLUMN_LANGGRAPH.md)。

---

## 1. LangChain 是什么？

**一句话**：围绕大语言模型（LLM）的 **组件库 + 编排方式**，把「提示词、模型调用、检索、工具、解析」等拆成 **可替换的模块**，并用统一接口 **组合成流水线**。

**注意**：日常说的「LangChain」常指**整个生态**，而不是单一 pip 包：

| 包名 | 角色 |
|------|------|
| **`langchain-core`** | 稳定抽象：`Runnable`、`BaseMessage`、`ChatPromptTemplate`、`BaseTool`、`BaseRetriever` 等 |
| **`langchain-openai`** 等 | 具体厂商的 Chat / Embeddings 实现 |
| **`langchain-community`** | 社区向量库、Loader、部分集成 |
| **`langchain`** | 高层封装、部分 Agent 便捷 API（随版本变化，核心能力多在 core） |
| **`langchain-text-splitters`** | 文本切分 |
| **`langchain-chroma`** 等 | 向量库官方/半官方集成 |

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
[LangChain 文档](https://python.langchain.com/docs/) · [Runnable 概念](https://python.langchain.com/docs/concepts/runnables/)

---

## 7. 与本项目对照

| 概念 | 本项目位置 |
|------|------------|
| LCEL RAG 链 | `src/agent.py` → `get_rag_chat_chain()` |
| 纯对话链 | `get_chat_chain()` 在 `USE_RAG=false` 时 |
| Prompt | `src/prompts.py` |
| 配置与模型 | `src/config.py`、`get_llm()` |
| 向量与检索 | `src/rag.py` |
| Tool 定义 | `src/tools/` |

---

*专栏为学习笔记性质，具体 API 以当前安装的包版本与官方文档为准。*
