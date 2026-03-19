"""
Agent 构建：当前为阶段1 — 仅 LLM 对话；后续阶段将加入 RAG Tool、MCP Tools 与 ReAct。
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from src.config import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    DEFAULT_LLM_MODEL,
    OPENAI_TIMEOUT,
)
from src.prompts import SYSTEM_PROMPT


def get_llm():
    """创建 LangChain ChatOpenAI 实例；若使用国产模型可在此替换为对应 LangChain 集成。"""
    # timeout：避免弱网下一默认超时过短；可在 .env 用 OPENAI_TIMEOUT 调整
    kwargs = {
        "model": DEFAULT_LLM_MODEL,
        "api_key": OPENAI_API_KEY,
        "timeout": OPENAI_TIMEOUT,
    }
    if OPENAI_API_BASE:
        kwargs["base_url"] = OPENAI_API_BASE
    return ChatOpenAI(**kwargs)


def get_chat_chain():
    """
    阶段1：简单对话链，带 System 与多轮历史。
    后续可替换为 create_react_agent + tools。
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )
    return prompt | llm


def chat(chain, user_input: str, history: list):
    """
    执行一轮对话。
    :param chain: get_chat_chain() 返回的 LCEL 链
    :param user_input: 用户当前输入
    :param history: 之前的 (HumanMessage, AIMessage) 列表，用于多轮
    :return: (AI 回复文本, 更新后的 history)
    """
    # 将 history 展平为 message 列表（LangChain 期望的格式）
    messages = []
    for h, a in history:
        messages.append(HumanMessage(content=h))
        messages.append(AIMessage(content=a))
    result = chain.invoke(
        {"input": user_input, "history": messages}
    )
    ai_text = result.content if hasattr(result, "content") else str(result)
    new_history = history + [(user_input, ai_text)]
    return ai_text, new_history
