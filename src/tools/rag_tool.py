"""
供阶段3 ReAct Agent 调用的知识库检索工具（阶段2 可先单独测试）。
"""
from langchain_core.tools import tool

from src.rag import format_retrieved_context, get_retriever


@tool
def search_health_knowledge(query: str) -> str:
    """
    根据用户问题检索本地健康知识库（公开医学常识、用药说明摘编、《本草纲目》相关常识等）。
    无相关条目时返回说明。回答用户前可先调用本工具获取依据。
    """
    retriever = get_retriever()
    docs = retriever.invoke(query)
    return format_retrieved_context(docs)
