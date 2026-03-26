# 健康助理智能体

基于 **Python + LangChain + MCP + RAG + ReAct** 的健康助理，用于学习与搭建智能体。

## 环境

- Python 3.11+（由 [mise](https://mise.jndev.com/) 管理）
- 依赖由 [Poetry](https://python-poetry.org/) 管理

## 快速开始

```bash
# 1. 安装 Python（若已安装 mise）
mise install

# 2. 安装依赖
poetry install

# 3. 配置 API Key（复制 .env.example 为 .env 并填写）
cp .env.example .env

# 4. 运行对话（默认 ReAct + 可选 RAG；见 .env）
poetry run python -m src.main
# 或
poetry run doctor-agent
```

### 阶段 4：MCP 文件系统（可选）

1. 安装 [Node.js](https://nodejs.org/)，确保终端能执行 **`npx`**。  
2. 在 **`.env`** 设置 **`USE_MCP=true`**（并保持 **`USE_REACT_AGENT=true`**）。  
3. 将允许 Agent 读取的文件放在 **`data/mcp_allowed/`**（或配置 **`MCP_FILESYSTEM_ROOT`**）。  
4. 启动后若成功，会看到 **`[MCP] 已连接 filesystem…`**；失败会降级为无 MCP，仅打印原因。  

原理与新手详解见 **[docs/PHASE4_LEARNING.md](./docs/PHASE4_LEARNING.md)**；操作与验收见 **[docs/PHASE4_RUN_FLOW.md](./docs/PHASE4_RUN_FLOW.md)**。

### 阶段 5：敏感提示、多轮历史上限、评测清单

1. **敏感场景**：`src/prompts.py` 的 System 中强化免责；若用户句命中急重症/诊断/处方等关键词，`src/sensitive_hint.py` 在**本轮**向模型附加 **【系统安全提示·仅本轮】**（`history` 中仍保存用户**原文**，避免重复堆叠提示）。  
2. **历史长度**：**`CHAT_HISTORY_MAX_TURNS`**（默认 `32`）只保留最近 N 轮对话。  
3. **关闭注入**（保留 System 合规）：**`SENSITIVE_HINT_ENABLED=false`**。

详解 **[docs/PHASE5_LEARNING.md](./docs/PHASE5_LEARNING.md)** · 验收 **[docs/PHASE5_RUN_FLOW.md](./docs/PHASE5_RUN_FLOW.md)** · 抽检用例 **[docs/eval_examples.md](./docs/eval_examples.md)**。

```bash
poetry run pytest tests/test_sensitive_hint.py -q
```

## 构建计划

详细分步见 **[BUILD_PLAN.md](./BUILD_PLAN.md)**，按阶段 0 → 1 → 2 → 3 → 4 → 5 推进；阶段 5 文档见上。

## 架构与目录

从研发与系统分层角度的说明见 **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**。  
阶段 4 流程说明见 **[docs/PHASE4_RUN_FLOW.md](./docs/PHASE4_RUN_FLOW.md)**。

## 项目结构（节选）

```
src/
├── main.py           # 入口
├── agent.py          # LCEL 链 / ReAct 图、历史截断、敏感注入
├── sensitive_hint.py # 阶段 5：关键词检测、本轮用户句前缀
├── prompts.py        # System Prompt
├── config.py         # 含 CHAT_HISTORY_MAX_TURNS 等
├── rag.py / rag_ingest.py
└── tools/            # 本地工具、RAG、MCP
```

## 免责声明

本助手仅作健康信息参考与生活助理，不替代医生诊断或处方，涉及用药与症状请咨询医生。
