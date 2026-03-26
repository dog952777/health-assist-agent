# 学习专栏索引：LangChain 与 LangGraph

两篇**并列专栏**，便于对照「组件/直线管道」与「有状态/可循环图」：

| 专栏 | 文件 | 核心一句话 |
|------|------|------------|
| **LangChain** | [COLUMN_LANGCHAIN.md](./COLUMN_LANGCHAIN.md) | Runnable + LCEL + 依赖包说明 + **`src/agent.py` 业务入口** + 阶段 1～4 对照 — **零件与直线编排** |
| **LangGraph** | [COLUMN_LANGGRAPH.md](./COLUMN_LANGGRAPH.md) | State + Node + 边 + **依赖子包** + **`src/agent.py` 图入口** + 阶段 3/4 — **分支与循环（典型 Agent）** |

**推荐阅读顺序**：

1. 先 **LangChain**，能解释你们 **阶段 2**（`get_rag_chat_chain`）。  
2. 再 **LangGraph**，能解释 **阶段 3**（`create_react_agent`、`chat_react`）。

**与本项目其它文档**：

- 阶段 2 运行流：[PHASE2_RUN_FLOW.md](./PHASE2_RUN_FLOW.md)  
- 阶段 3 运行流 + `invoke` 细化：[PHASE3_RUN_FLOW.md](./PHASE3_RUN_FLOW.md)  
- 阶段 3 知识点与自测：[PHASE3_LEARNING.md](./PHASE3_LEARNING.md)  
- 阶段 4 MCP（原理详解）：[PHASE4_LEARNING.md](./PHASE4_LEARNING.md)  
- 阶段 4 MCP（操作与验收）：[PHASE4_RUN_FLOW.md](./PHASE4_RUN_FLOW.md)  
- 构建计划：[BUILD_PLAN.md](../BUILD_PLAN.md)
