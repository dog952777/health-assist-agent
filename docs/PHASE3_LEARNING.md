# 阶段 3 新手向知识点总结

> 面向：已理解 **阶段 2（固定 RAG 链）**，要学习 **ReAct Agent + 工具** 的同学。  
> 对应本项目：**`USE_REACT_AGENT=true`（默认）** + `langgraph.prebuilt.create_react_agent` + `tools/` + `agent.get_react_agent()` / `chat_react()`。  
> 构建计划见 **[BUILD_PLAN.md](../BUILD_PLAN.md)** 阶段 3；阶段 2 知识点见 **[PHASE2_LEARNING.md](./PHASE2_LEARNING.md)**。

---

## 1. 阶段 3 在解决什么问题？

| 概念 | 是什么 | 做什么用 | 为什么要用 |
|------|--------|----------|------------|
| **阶段 2（对比）** | **每轮**用户说完话，链里**固定**先检索再生成 | 简单、行为确定 | 与问题无关也会检索，浪费延迟与 token；闲聊不该乱查库 |
| **阶段 3（ReAct + Tool）** | 模型根据当前话**决定**是否调用工具、调哪个、是否多步 | 「该查库才查」「该算才算」「该看时间才看时间」 | 更接近产品里「智能助理」的交互；工具可扩展（日历、MCP 等） |
| **Tool（工具）** | 带名称、说明、参数 schema 的可调用能力，由**模型发指令**触发 | 检索、取时间、计算等 | 把「能力」从 Prompt 里解放出来，结构化、可测试、可组合 |
| **ReAct** | **Reasoning + Acting**：推理与执行交替，可循环多轮 | 先想再动，读完工具结果再答 | 单轮 Prompt 塞不下复杂流程；需要「调用—看结果—再推理」 |

---

## 2. LangChain Tool：从函数到「模型可调用的能力」

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **`@tool` 装饰器** | 把普通 Python 函数包成 `BaseTool` | 统一给 Agent 使用 | 少写样板代码 |
| **函数 docstring** | 工具的**自然语言说明** | 模型靠它判断「何时、为何」调用 | **阶段 3.4 的核心**：说明不清 → 乱调、漏调 |
| **`name` / `args_schema`** | 工具名与参数结构 | API 侧 function calling | 与 OpenAI 兼容接口的 tools 格式对齐 |
| **单独测试** | `tool.invoke({"query": "..."})` 等 | 不经过 LLM 先验证工具逻辑 | 排错时区分「工具坏了」还是「模型选错」 |

**对照代码**：`src/tools/rag_tool.py`（`search_health_knowledge`）、`src/tools/basic_tools.py`（`get_current_datetime`、`calculator`）。

---

## 3. 聊天模型与 Tool Calling（底层在发生什么）

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **Tool Calling** | 模型输出结构化「要调哪个工具 + 参数」 | 由运行时执行函数，再把结果写回上下文 | 比让模型「假装」输出 JSON 更可靠（由 API 规范） |
| **`AIMessage.tool_calls`** | 助理消息里附带的调用列表 | 框架据此执行 `ToolNode` | 多工具、多参数时靠它路由 |
| **`ToolMessage`** | 承载单次工具执行结果的消息 | 拼进下一轮模型的输入 | 模型必须「看到」工具输出才能继续推理 |
| **`bind_tools`** | 把 tools schema 绑到模型上 | 预置 Agent 内部会用 | 理解即可；不必在每个项目里手写循环 |

**Why**：ReAct 在工程上就是「模型 → tool_calls → 执行 → 新消息 → 模型 → … → 最终自然语言」。

---

## 4. LangGraph 与 `create_react_agent`

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **LangGraph** | 用**图**描述状态与节点（模型、工具、条件边） | 比一条直线 LCEL 更适合「分支、循环」 | Agent 本质是**有环**的控制流 |
| **`create_react_agent`** | 预置「聊天模型节点 + 工具节点 + 结束条件」 | 快速得到可 `invoke` 的 **CompiledGraph** | 不必从零画 ReAct 图 |
| **状态键 `messages`** | 图状态里通常是消息列表 | `invoke({"messages": [...]})` | 与 Chat 多轮一致，便于加历史 |
| **`invoke` vs LCEL** | 图也是 Runnable | 一次 `invoke` 可能内部多步（多次模型 + 工具） | 延迟与计费可能高于「单链一次 completion」 |
| **`prompt=`** | 注入系统层行为（如工具路由规则） | 与阶段 2 的 `SYSTEM_PROMPT` 衔接 | 减少胡编、减少乱用工具 |

**对照代码**：`src/agent.py` 中 `get_react_agent()`、`chat_react()`；`src/prompts.py` 中 `REACT_AGENT_PROMPT`。

---

## 5. System Prompt 设计（BUILD_PLAN 3.4）

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **工具路由规则** | 明确「哪类用户话 → 哪个工具」 | 提高召回正确工具的概率 | 模型不会读你心里的产品文档 |
| **禁止过度调用** | 如：闲聊可直接答，不必检索 | 省 token、省延迟、少噪声片段 | 否则「你好」也去搜向量库 |
| **空结果 / 失败** | 要求诚实说明 + 医疗场景兜底 | 用户体验与安全 | 避免模型在没证据时编造医学细节 |
| **与 `SYSTEM_PROMPT` 拼接** | 人设 + 工具策略两条线合一 | `REACT_AGENT_PROMPT` | 角色边界与工具策略都要稳定 |

**对照代码**：`src/prompts.py`（`REACT_AGENT_SYSTEM`、`REACT_AGENT_PROMPT`）。

---

## 6. 与阶段 2 RAG 的衔接

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **同一 Retriever** | `get_retriever()` 仍来自 `rag.py` | 链与 Tool 共用检索逻辑 | 不重复维护两套索引 |
| **链 vs 工具** | 阶段 2：`RunnableLambda` 里固定 `retriever.invoke`；阶段 3：仅当模型调用 `search_health_knowledge` 时检索 | 控制**何时**发生检索 | 产品行为从「总是」变为「按需」 |
| **`USE_RAG` + `USE_REACT_AGENT`** | 两个独立开关 | 组合出四种模式（纯 LLM / 固定 RAG / ReAct 无库 / ReAct+库） | 调试时快速对比 |
| **懒加载向量库** | ReAct 模式下启动可不预加载 Chroma | 第一次真正调用检索工具时再 `get_vectorstore()` | 仅用时间/计算工具时不必有知识文件 |

**对照代码**：`src/config.py`、`src/agent.py`（`get_react_tools`）、`src/main.py`。

---

## 7. 工程与排错（建议掌握）

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **多步调用** | 一轮用户输入可能触发多次模型 API | 成本与延迟上升 | 上线要预算与超时 |
| **模型能力差异** | 小模型工具 JSON 不稳、不爱停 | 换模型或减工具数量 | 与业务 SLA 相关 |
| **网络 / 代理 / SSL** | 错误可能出现在 Agent 循环的任一步 | 与阶段 1、2 同类问题 | 栈更深，需看**最底层** `ConnectError` 等 |
| **验收用例** | 固定几句：时间、计算、用药知识 | 回归工具选择与回答质量 | 避免「感觉能跑」 |

---

## 8. 与本项目文件的映射（复习清单）

| 主题 | 文件 |
|------|------|
| 工具定义 | `src/tools/rag_tool.py`、`src/tools/basic_tools.py` |
| 工具导出 | `src/tools/__init__.py` |
| ReAct 图与多轮 | `src/agent.py` |
| Prompt | `src/prompts.py` |
| 开关 | `src/config.py` |
| CLI | `src/main.py` |
| 向量与检索（与阶段 2 共用） | `src/rag.py`、`src/rag_ingest.py` |

---

## 9. 可选加深（阶段 4 以前）

- **自定义 LangGraph**：不用 `create_react_agent`，自己定义 State、节点与条件边。  
- **Human-in-the-loop**：敏感工具执行前中断等待人工确认。  
- **评测**：记录「是否选对工具」「最终回答是否引用检索片段」。

---

## 10. 自测题（建议先闭卷再想答案）

### 题目

1. **`@tool` 的 docstring 为什么会影响 Agent 行为？**  
2. **`chat_react` 里为什么要传 `messages` 列表，而不是像阶段 2 那样只传 `input` + `history` 占位？**  
3. **阶段 2 的链和阶段 3 的 Agent，「检索」发生的时机有什么不同？**  
4. **若 `USE_RAG=false` 但 `USE_REACT_AGENT=true`，工具列表里会少什么？对用户问「布洛芬用法」可能有什么后果？**  
5. **为什么说 ReAct 一轮对话可能消耗比阶段 2 更多的 API 调用次数？**

---

### 参考答案

1. **docstring 会作为工具描述提供给模型**（function calling 里的 description）。模型靠它判断「什么时候该调用、参数语义是什么」。写得太泛或太像闲聊，会导致**漏调、乱调、参数胡写**。  
2. **LangGraph 预置 ReAct 图的状态约定是 `messages`**：里面要容纳 **Human / AI（含 tool_calls）/ Tool** 等完整轨迹，才能多步循环。阶段 2 用 `ChatPromptTemplate` 的 `history` 占位符是另一条 LCEL 路径；阶段 3 把历史转成 `HumanMessage`/`AIMessage` 再 `invoke`，与图的输入契约一致。  
3. **阶段 2**：每轮用户话一到，链里**固定** `retriever.invoke(当前句)` 再生成。**阶段 3**：只有模型决定调用 `search_health_knowledge` 时才检索；纯闲聊可能**完全不查库**。  
4. **`get_react_tools()` 在 `USE_RAG` 为 false 时不会加入 `search_health_knowledge`**，只剩时间与计算器。用户问布洛芬用法时，模型**没有检索工具**，只能凭参数知识回答，**更容易幻觉**；合规上应提示用户咨询医生，且不应编造剂量。  
5. **ReAct 可能在一次用户轮次内多次调用模型**：例如「先输出 tool_calls → 执行工具 → 再调模型生成最终答案」。阶段 2 的典型链通常是「一次检索 + **一次**生成」（除非你自己加循环）。

---

## 11. 延伸阅读

- **LangChain / LangGraph 双专栏（原理与应用）**：[COLUMNS_INDEX.md](./COLUMNS_INDEX.md)  
- **流程图 + 单次 invoke 逐步推演**：[PHASE3_RUN_FLOW.md](./PHASE3_RUN_FLOW.md)（含 **§8 messages 推演**、与 `history` 的关系）。  
- 官方文档：[LangGraph](https://langchain-ai.github.io/langgraph/) 预置 Agent、ToolNode。  
- 本项目 **BUILD_PLAN** 阶段 3 验收标准；README 中阶段 3 说明（若有）。
