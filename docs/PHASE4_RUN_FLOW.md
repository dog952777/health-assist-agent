# 阶段 4：MCP（filesystem）接入与合并到 ReAct Agent

> **新手系统理解 MCP / RAG 差异 / stdio 与 HTTP / tool_name_prefix** 见 **[PHASE4_LEARNING.md](./PHASE4_LEARNING.md)**（偏原理与比喻）；本文偏 **操作与代码路径**。  
> **阶段 4 模块依赖简图（Mermaid + ASCII）**：打开 [PHASE4_LEARNING.md](./PHASE4_LEARNING.md) 搜索 **「附录：阶段 4 模块依赖简图」**。

## 目标

- 用 **stdio** 启动官方 **`@modelcontextprotocol/server-filesystem`**。
- 通过 **`langchain-mcp-adapters`** 的 **`MultiServerMCPClient.get_tools()`** 转为 LangChain **`BaseTool`**。
- 与现有 **`get_current_datetime` / `calculator` / `search_health_knowledge`** 合并，交给 **`create_react_agent`**。

## 配置（`.env`）

| 变量 | 说明 |
|------|------|
| **`USE_MCP=true`** | 启用 MCP；启动时会尝试 `npx` 拉取并运行 filesystem server |
| **`MCP_FILESYSTEM_ROOT`** | 可选，默认 **`data/mcp_allowed`**（相对项目根）；MCP 仅能访问此目录下文件 |
| **`MCP_NPX_COMMAND`** | 可选，默认 **`npx`**；Windows 若找不到命令可改为 **`npx.cmd`** 或 Node 安装路径下的可执行文件 |

还需本机安装 **Node.js**，且终端能执行 **`npx`**（首次会下载 `@modelcontextprotocol/server-filesystem`）。

## 代码路径

1. **`src/config.py`**：`MCP_SERVER_CONNECTIONS` → `fs` → `stdio` + `npx -y @modelcontextprotocol/server-filesystem <ROOT>`  
2. **`src/tools/mcp_tools.py`**：`asyncio.run(client.get_tools())`，**`tool_name_prefix=True`** → 工具名多为 **`fs_*`**  
3. **`src/agent.py`**：`get_react_tools()` 在 **`USE_MCP`** 时 `extend` MCP 工具；**`_react_system_prompt()`** 追加 **`REACT_AGENT_MCP_HINT`**  
4. **`src/prompts.py`**：`REACT_AGENT_MCP_HINT` 说明 fs_* 与知识库检索的区别  

## 验收建议

1. 在 **`data/mcp_allowed/`** 放测试文件（如 `用药备忘示例.txt`）。  
2. 启动：`USE_MCP=true`、`USE_REACT_AGENT=true`，运行 `poetry run python -m src.main`。  
3. 应看到 **`[MCP] 已连接 filesystem，加载 N 个工具`**。  
4. 提问：「请列出 mcp_allowed 里有哪些文件」或「读一下 用药备忘示例.txt」— 模型应调用 **`fs_*`** 工具。  

## 故障排查

- **加载失败**：终端是否可执行 `npx`；代理/防火墙是否拦截 npm；可将 **`MCP_NPX_COMMAND`** 设为绝对路径。  
- **未加载 MCP 仍可用**：失败时打印警告并 **降级为无 MCP**，仅本地工具 + RAG。  

## 与 BUILD_PLAN 的差异说明

- **「明天 8 点吃药提醒」** 通常需要 **日历类 MCP 或其它集成**，本阶段以 **filesystem** 为主，便于本地复现。  
- 后续可在 **`MCP_SERVER_CONNECTIONS`** 中增加第二个 server（如 memory/calendar），同样 **`get_tools()`** 合并即可。
