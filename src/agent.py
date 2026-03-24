"""
Agent 构建：阶段1 纯 LLM；阶段2 RAG 链（每轮先检索）；阶段3 ReAct + Tools（LangGraph，按需调工具）。
"""
from collections import Counter

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from src.config import (
    DEFAULT_LLM_MODEL,
    OPENAI_API_BASE,
    OPENAI_API_KEY,
    OPENAI_TIMEOUT,
    REACT_VERBOSE,
    USE_RAG,
)
from src.prompts import RAG_CONTEXT_SYSTEM, REACT_AGENT_PROMPT, SYSTEM_PROMPT


def get_llm():
    """创建 LangChain ChatOpenAI 实例；若使用国产模型可在此替换为对应 LangChain 集成。"""
    kwargs = {
        "model": DEFAULT_LLM_MODEL,
        "api_key": OPENAI_API_KEY,
        "timeout": OPENAI_TIMEOUT,
    }
    if OPENAI_API_BASE:
        kwargs["base_url"] = OPENAI_API_BASE
    return ChatOpenAI(**kwargs)


def _plain_prompt():
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )


def get_chat_chain():
    """
    阶段1/2：非 ReAct 模式下的 LCEL 链。
    USE_RAG 为真时每轮固定检索后再生成；为假时仅 system + 历史 + 用户句。
    """
    if USE_RAG:
        return get_rag_chat_chain()
    llm = get_llm()
    return _plain_prompt() | llm


def get_rag_chat_chain():
    """
    阶段2：对用户当前句做相似检索，将片段注入第二条 system，再交给 LLM。
    """
    from src.rag import format_retrieved_context, get_retriever

    llm = get_llm()
    retriever = get_retriever()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("system", RAG_CONTEXT_SYSTEM),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )

    def attach_context(inputs: dict) -> dict:
        # 仅用当前用户句检索，避免把整段历史拼进向量查询导致噪声
        docs = retriever.invoke(inputs["input"])
        return {
            **inputs,
            "context": format_retrieved_context(docs),
        }

    return RunnableLambda(attach_context) | prompt | llm


def get_react_tools():
    """阶段3：按配置组装工具（时间、计算器；可选知识库检索）。"""
    from src.tools.basic_tools import calculator, get_current_datetime
    from src.tools.rag_tool import search_health_knowledge

    tools = [get_current_datetime, calculator]
    if USE_RAG:
        tools.append(search_health_knowledge)
    return tools


def get_react_agent():
    """
    阶段3：LangGraph 预置 ReAct 图；模型在「思考—调工具—再思考」循环中结束于最终答复。
    """
    from langgraph.prebuilt import create_react_agent

    llm = get_llm()
    tools = get_react_tools()
    return create_react_agent(llm, tools, prompt=REACT_AGENT_PROMPT)


def _message_content_to_text(content) -> str:
    """兼容部分模型返回 str 或内容块列表的 message.content。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content) if content else ""


def _final_assistant_text(messages: list) -> str:
    """从完整消息列表中取最后一条带正文的助理消息。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = _message_content_to_text(msg.content).strip()
            if text:
                return text
    return ""


def _message_type_cn(msg) -> str:
    """日志用：消息类型中文简称。"""
    if isinstance(msg, HumanMessage):
        return "用户 HumanMessage"
    if isinstance(msg, AIMessage):
        return "助理 AIMessage"
    if isinstance(msg, ToolMessage):
        return "工具结果 ToolMessage"
    return type(msg).__name__


def _describe_message_tail(msg, *, preview: int = 100) -> str:
    """日志用：描述单条消息要点（tool_calls / 正文预览）。"""
    if isinstance(msg, AIMessage):
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:

            def _tc_name(tc) -> str:
                if isinstance(tc, dict):
                    return tc.get("name", "?")
                return getattr(tc, "name", "?")

            names = [_tc_name(tc) for tc in tool_calls]
            body = _message_content_to_text(msg.content).strip()
            tail = (body[:preview] + "…") if len(body) > preview else body
            return f"请求工具 {names} | 同时正文预览: {tail!r}" if tail else f"请求工具 {names} | 正文为空"
        body = _message_content_to_text(msg.content).strip()
        shown = (body[:preview] + "…") if len(body) > preview else body
        return f"最终回复预览: {shown!r}"
    if isinstance(msg, ToolMessage):
        body = _message_content_to_text(msg.content)
        name = getattr(msg, "name", "") or "?"
        prev = (body[:preview] + "…") if len(body) > preview else body
        return f"供模型读取的返回值 (关联工具名≈{name}) 长度={len(body)} 预览: {prev!r}"
    if isinstance(msg, HumanMessage):
        body = (msg.content or "") if isinstance(msg.content, str) else str(msg.content)
        shown = (body[:preview] + "…") if len(body) > preview else body
        return f"预览: {shown!r}"
    return repr(msg)[:preview]


def _log_react_step(step: int, msgs: list) -> None:
    """REACT_VERBOSE：打印本步结束后消息统计与最后一条摘要。"""
    counts = Counter(_message_type_cn(m).split()[0] for m in msgs)
    parts = [f"{k}×{v}" for k, v in sorted(counts.items())]
    print(f"  [步骤 {step}] 消息总数={len(msgs)} | 类型计数: {', '.join(parts)}", flush=True)
    if msgs:
        last = msgs[-1]
        print(f"           末条 [{_message_type_cn(last)}] {_describe_message_tail(last)}", flush=True)


def _log_full_message_chain(msgs: list) -> None:
    """REACT_VERBOSE：打印本轮结束后完整 messages 序号，便于对照 tool_calls / ToolMessage。"""
    print("  --- 本轮结束后完整消息链（按顺序）---", flush=True)
    if not msgs:
        print("  （空）", flush=True)
        return
    for i, m in enumerate(msgs, 1):
        print(f"  [{i}] {_message_type_cn(m)} | {_describe_message_tail(m, preview=120)}", flush=True)


def _run_react_graph(agent_graph, messages: list) -> dict:
    """
    执行 ReAct 图。REACT_VERBOSE 时用 stream 跟踪；并在结束时打印完整消息链。
    说明：create_react_agent 等预置图在部分版本下 stream_mode=values 可能只在流程末尾 yield 一次，
    因此除逐步摘要外，末尾会再打一遍「完整消息链」保证能看见 tool_calls 全过程。
    """
    if not REACT_VERBOSE:
        return agent_graph.invoke({"messages": messages})

    print("\n======== ReAct 调试 (REACT_VERBOSE=true) ========", flush=True)
    print(f"进入图前 messages 条数: {len(messages)}", flush=True)
    final_state: dict | None = None
    step = 0
    try:
        for state in agent_graph.stream({"messages": messages}, stream_mode="values"):
            step += 1
            final_state = state
            _log_react_step(step, state.get("messages", []))
    except Exception as exc:
        print(f"  [警告] stream 异常，将 fallback 为 invoke: {type(exc).__name__}: {exc}", flush=True)
        final_state = None

    if final_state is None:
        print("  （stream 无产出或失败，使用 invoke 执行一次）", flush=True)
        final_state = agent_graph.invoke({"messages": messages})
        if step == 0:
            _log_react_step(1, final_state.get("messages", []))

    _log_full_message_chain(final_state.get("messages", []))
    print("======== ReAct 调试结束 ========\n", flush=True)
    return final_state


def chat(chain, user_input: str, history: list):
    """
    执行一轮对话（LCEL 链）。
    :param chain: get_chat_chain() 返回的 Runnable
    :param history: 之前的 (用户原文, 助理原文) 元组列表
    """
    messages = []
    for h, a in history:
        messages.append(HumanMessage(content=h))
        messages.append(AIMessage(content=a))
    result = chain.invoke({"input": user_input, "history": messages})
    ai_text = result.content if hasattr(result, "content") else str(result)
    new_history = history + [(user_input, ai_text)]
    return ai_text, new_history


def chat_react(agent_graph, user_input: str, history: list):
    """
    执行一轮 ReAct 对话（CompiledGraph）。
    :param agent_graph: get_react_agent() 返回值
    :param history: 之前的 (用户原文, 助理原文) 元组列表
    """
    messages = []
    for h, a in history:
        messages.append(HumanMessage(content=h))
        messages.append(AIMessage(content=a))
    messages.append(HumanMessage(content=user_input))
    result = _run_react_graph(agent_graph, messages)
    ai_text = _final_assistant_text(result["messages"])
    if not ai_text:
        ai_text = "（本轮未生成可见答复，请重试或简化问题。）"
    new_history = history + [(user_input, ai_text)]
    return ai_text, new_history
