"""
阶段 4：通过 langchain-mcp-adapters 连接 MCP Server（默认 stdio + @modelcontextprotocol/server-filesystem），
将 MCP 工具转为 LangChain Tool 并并入 ReAct Agent。
"""
from __future__ import annotations

import asyncio
import logging
import warnings
from typing import Any

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# 进程内缓存：避免每次 get_react_tools 都 asyncio.run 拉取工具列表
_mcp_tools_cache: list[BaseTool] | None = None
_mcp_load_attempted: bool = False


def _load_mcp_tools_via_client(connections: dict[str, Any]) -> list[BaseTool]:
    """在无异步事件循环的上下文中启动 asyncio，拉取所有 MCP 工具。"""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def _fetch() -> list[BaseTool]:
        # langchain-mcp-adapters 0.1.x：无 tool_name_prefix；工具名多为 MCP 服务端原名（如 read_file）
        client = MultiServerMCPClient(connections)
        return await client.get_tools()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_fetch())
    # 已在异步上下文中（少见）：新建循环策略在部分环境不可靠，直接提示
    msg = "当前线程已有 asyncio 事件循环，无法在同步函数中加载 MCP 工具；请从同步入口（如 python -m src.main）启动。"
    raise RuntimeError(msg)


def _bind_sync_from_coroutine(coro):
    """
    MCP 适配器常见：StructuredTool 仅有 coroutine，无 func。
    LangGraph 预置 ReAct 的 ToolNode 会同步调用 tool.invoke → 报
    NotImplementedError('StructuredTool does not support sync invocation.')。
    本进程入口为同步 CLI，用 asyncio.run 包一层即可（无嵌套事件循环）。
    """

    def _sync(**kwargs: Any) -> Any:
        return asyncio.run(coro(**kwargs))

    return _sync


def _patch_mcp_tools_for_sync_langgraph(tools: list[BaseTool]) -> list[BaseTool]:
    """为仅异步的 MCP 工具补全 sync func，供同步 CompiledGraph.invoke 使用。"""
    patched: list[BaseTool] = []
    for t in tools:
        coro = getattr(t, "coroutine", None)
        func = getattr(t, "func", None)
        if coro is None or func is not None:
            patched.append(t)
            continue
        model_copy = getattr(t, "model_copy", None)
        if not callable(model_copy):
            patched.append(t)
            continue
        try:
            patched.append(t.model_copy(update={"func": _bind_sync_from_coroutine(coro)}))
        except Exception:
            patched.append(t)
    return patched


def get_mcp_tools_or_empty() -> list[BaseTool]:
    """
    返回 MCP 转换后的 LangChain 工具列表；失败时返回 [] 并缓存，避免反复 spawn npx。
    仅在 config.USE_MCP 为真时由 get_react_tools 调用。
    """
    global _mcp_tools_cache, _mcp_load_attempted

    if _mcp_load_attempted:
        return list(_mcp_tools_cache or [])

    _mcp_load_attempted = True
    from src.config import MCP_SERVER_CONNECTIONS, USE_MCP

    if not USE_MCP or not MCP_SERVER_CONNECTIONS:
        _mcp_tools_cache = []
        return []

    try:
        tools = _patch_mcp_tools_for_sync_langgraph(
            _load_mcp_tools_via_client(MCP_SERVER_CONNECTIONS)
        )
        _mcp_tools_cache = tools
        names = [t.name for t in tools]
        logger.info("MCP 已加载 %s 个工具: %s", len(tools), names)
        print(
            f"[MCP] 已连接 filesystem，加载 {len(tools)} 个工具（示例: {names[:5]}{'...' if len(names) > 5 else ''}）",
            flush=True,
        )
        return list(tools)
    except Exception as exc:
        _mcp_tools_cache = []
        warnings.warn(
            f"MCP 工具加载失败，将继续使用本地工具（无 MCP）。原因: {exc!s}",
            UserWarning,
            stacklevel=2,
        )
        print(
            f"[MCP] 加载失败（已跳过 MCP）: {type(exc).__name__}: {exc}\n"
            "请确认已安装 Node.js、可在终端执行 npx，且 MCP_FILESYSTEM_ROOT 路径有效。"
            "详见 docs/PHASE4_RUN_FLOW.md",
            flush=True,
        )
        return []
