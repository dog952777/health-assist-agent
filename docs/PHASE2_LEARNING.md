# 阶段 2 新手向知识点总结

> 面向：已经跑通**阶段 1**，想理解 **RAG + 本地向量库** 在做什么的同学。  
> 对应本项目：**`USE_RAG=true`（默认）**，`rag.py` + `rag_ingest.py` + `agent.get_rag_chat_chain()` + `data/knowledge` + `data/chroma_db`。

---

## 1. RAG 是什么？解决什么问题？

| 概念 | 是什么 | 做什么用 | 为什么要用 |
|------|--------|----------|------------|
| **RAG（Retrieval-Augmented Generation）** | **先检索**与你的问题相关的文本片段，再把这些片段**塞进提示词**，让模型**对着材料说话** | 回答有据可查、可引用本地知识 | 纯 LLM 容易「幻觉」；医疗/合规场景更需要**可溯源**的参考 |
| **检索（Retrieval）** | 从一大堆文档里找出**最相关**的几段 | 缩小模型要看的范围 | 模型上下文有限，不能每次塞整本书 |
| **生成（Generation）** | LLM 根据「人设 + 检索片段 + 用户问题」写回答 | 输出自然语言 | 检索结果是碎片，需要模型**归纳、对照用户问题**表达 |
| **本项目阶段 2 的形态** | **每轮**用**当前用户这句话**去查向量库，把结果作为**第二条 system** 注入，再调 Chat | 实现「自动 RAG」，用户无需说「请查库」 | 先简单跑通；阶段 3 再让模型**自己决定**何时检索（ReAct + Tool） |

---

## 2. 从文件到「能搜」：索引流水线

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **原始文档（`data/knowledge`）** | `.md` / `.txt` 等人类可读文件 | 你维护的「知识来源」 | 与代码分离；换内容只改文件 + 重建索引 |
| **Document Loader（如 `TextLoader`）** | 把文件读成 LangChain 的 **`Document`**（正文 + metadata） | 统一后续处理接口 | 不同格式（PDF、网页）可换不同 Loader |
| **metadata（元数据）** | 每条文档附带的结构化信息（如 `source: 文件名`） | 回答里可追溯「来自哪份材料」 | 调试、审计、用户信任 |
| **文本切分（Text Splitting）** | 把长文切成多个 **chunk**（块） | 每块长度适合向量和检索 | 太大：语义杂、embedding 不准；太小：上下文碎 |
| **chunk_size / chunk_overlap** | 每块大约多少字；相邻块重复多少字 | 控制粒度与连续性 | overlap 减少「刚好切在句子中间」导致语义断裂 |
| **ingest / 建索引** | 对所有 chunk 调 **Embedding API** 得到向量，写入 **向量库** | **离线**算好，在线只查 | 对话时若每次都全文算向量会极慢、极贵 |
| **`rag_ingest` / `health-ingest`** | 强制**删旧库或覆盖**后全量重建 | 你改了知识文件后刷新索引 | 否则模型还在用**旧内容**的向量 |

---

## 3. 向量、Embedding、向量库（Chroma）

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **Embedding（嵌入）** | 把一段文字变成**固定维度的数字向量**（一串 float） | 表示「语义」；语义相近的文本向量距离近 | 计算机不能直接「理解」字义，向量便于**算相似度** |
| **Embedding 模型** | 专门把文本编码成向量的模型（与「聊天模型」不同） | `embed_documents` / `embed_query` | **聊天模型**负责说话；**向量模型**负责「搜相似」；本项目用 `EMBEDDING_MODEL` 配置 |
| **向量数据库 / 向量库** | 存「向量 + 原文 + metadata」，支持相似度搜索 | 毫秒级找出 Top-K 相似块 | 文档上千上万时，暴力遍历不现实 |
| **Chroma（本项目）** | 一种可**持久化到本地目录**的向量库 | `data/chroma_db`，免费、易上手 | 学习与小项目够用；生产可换 Qdrant、Milvus 等 |
| **collection（集合）** | 库内的一组向量数据（有名字） | 本项目固定名 `health_assistant_kb` | 同一目录可多集合；名称读写要一致 |
| **相似度检索 / Top-K** | 按与查询向量的距离排序，取前 **K** 条 | `RAG_TOP_K` 控制条数 | K 太小：信息不够；K 太大：噪声多、占上下文 |

---

## 4. 对话时发生了什么？（与阶段 1 的差异）

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **Retriever** | 封装「给一句 query → 返回若干 `Document`」 | `get_retriever()` 供链和 Tool 使用 | 统一检索接口，链和 Agent 都能复用 |
| **只用当前 `input` 检索** | 不用整段聊天历史去算向量 | 查询更聚焦 | 历史拼进 query 易引入噪声；需要时阶段 3 可做「查询改写」 |
| **`RAG_CONTEXT_SYSTEM`（`prompts.py`）** | 第二条 system，里面有 **`{context}`** | 告诉模型：下面是检索片段，怎么使用 | 与「人设 system」分离：**规则**与**材料**分层，好维护 |
| **`RunnableLambda(attach_context)`** | LCEL 里先执行 Python 函数：检索 → 填 `context` | 把检索结果注入模板 | 阶段 1 是 `prompt \| llm`；阶段 2 是 **`lambda \| prompt \| llm`** |
| **一轮对话两次「模型侧」调用** | ① Embedding 接口（把用户问题变成向量）② Chat 接口（生成回复） | 先搜后答 | 成本与延迟都比纯聊天高；这是 RAG 的常态 |

---

## 5. 配置与排错（你很可能踩的坑）

| 知识点 | 是什么 | 做什么用 | 为什么要用 |
|--------|--------|----------|------------|
| **`LLM_MODEL` vs `EMBEDDING_MODEL`** | 两个不同模型名 | 一个聊天、一个向量化 | 填反或混用会 404 / 400 |
| **百炼 + OpenAI 兼容** | 同一 `base_url` 走两套能力 | 少配一套网关 | 注意百炼**不支持** OpenAI 的 `text-embedding-3-small` 等名 |
| **`check_embedding_ctx_length=False`（百炼）** | LangChain 默认会把文本切成 **token 整数**再请求；百炼只认 **字符串列表** | 避免 `input.contents` 类 400 | 兼容层不是 100% 等价 OpenAI 行为 |
| **空 chunk** | 分段后某块只有空白 | 可能触发奇怪 API 报错 | 代码里会过滤空块 |
| **Chroma 遥测报错** | `capture() takes 1 positional argument...` | 统计上报失败 | **一般不影响**建库与检索；可忽略或升级 chromadb / 关遥测 |

---

## 6. `search_health_knowledge`（Tool）和自动 RAG 的区别

| 方式 | 是什么 | 现阶段在本项目 |
|------|--------|----------------|
| **自动 RAG（阶段 2）** | 每条用户消息**先检索再生成** | `get_rag_chat_chain()`，CLI 默认走这条 |
| **`search_health_knowledge` Tool** | 显式「工具」：给 query 返回检索文本 | 给**阶段 3 ReAct** 用，由 Agent **决定何时调用** |

两者底层都用 **`get_retriever()`**；差别在**谁触发检索**（固定每轮 vs 模型决策）。

---

## 7. 和阶段 1、阶段 3 的关系

| 阶段 | 重点 | 阶段 2 多了什么 |
|------|------|-----------------|
| **1** | LLM + 多轮 + 人设 | 无向量、无检索 |
| **2** | + 本地知识 + Chroma + 注入 context | 回答可对齐 `data/knowledge` |
| **3（计划）** | + ReAct + 多工具 + 可选 MCP | Tool 显式调用、步骤可观测 |

---

## 8. 建议你做的练习

1. 在 `data/knowledge` **加一小段**只有你认识的文字，跑 `rag_ingest`，再问模型相关问题，看是否**引用到那段**。  
2. 把 **`RAG_TOP_K`** 改成 `1` 和 `8`，对比回答**信息量与跑题**程度。  
3. 故意把 **`chunk_size`** 改很小（如 100），观察检索片段是否**更碎**。  
4. 阅读 [PHASE2_RUN_FLOW.md](./PHASE2_RUN_FLOW.md) 里的时序图，标出 **Embedding 调用**与 **Chat 调用**各一次。

---

## 相关文档

- 运行与数据流图：[PHASE2_RUN_FLOW.md](./PHASE2_RUN_FLOW.md)  
- LangChain 原理与应用专栏：[COLUMNS_INDEX.md](./COLUMNS_INDEX.md)（含 LangGraph 对照）  
- 阶段 1 概念衔接：[PHASE1_LEARNING.md](./PHASE1_LEARNING.md)  
- 架构总览：[ARCHITECTURE.md](./ARCHITECTURE.md)  
- 构建路线图：[../BUILD_PLAN.md](../BUILD_PLAN.md)  

---

*有具体报错可把终端完整输出对照 README「阶段 2」与本文第 5 节排查。*
