"""
阶段2：从 data/knowledge 加载文档，写入本地 Chroma，提供检索与 RAG 链依赖的 retriever。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings

from src.config import (
    CHROMA_PERSIST_DIR,
    EMBEDDING_MODEL,
    KNOWLEDGE_DIR,
    OPENAI_API_BASE,
    OPENAI_API_KEY,
    OPENAI_IS_DASHSCOPE_COMPAT,
    OPENAI_TIMEOUT,
    RAG_TOP_K,
)

# Chroma 集合名（加载与写入需一致）
CHROMA_COLLECTION_NAME = "health_assistant_kb"

# 全局缓存：避免重复加载向量库与 embedding 客户端
_embeddings: OpenAIEmbeddings | None = None
_vectorstore: Chroma | None = None


def clear_vectorstore_cache() -> None:
    """重建索引后调用，避免进程内仍持有旧的向量库实例。"""
    global _vectorstore
    _vectorstore = None


def _get_embeddings() -> OpenAIEmbeddings:
    """与 Chat 共用同一 base_url / key，便于百炼等 OpenAI 兼容接口。"""
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    kwargs: dict = {
        "model": EMBEDDING_MODEL,
        "openai_api_key": OPENAI_API_KEY,
        # OpenAIEmbeddings 使用 request_timeout，与 ChatOpenAI 的 timeout 区分
        "request_timeout": OPENAI_TIMEOUT,
    }
    if OPENAI_API_BASE:
        kwargs["openai_api_base"] = OPENAI_API_BASE
    # 百炼兼容接口要求 input 为 str 或 list[str]；LangChain 默认会按 tiktoken 切块并传 int[]，触发 400
    if OPENAI_IS_DASHSCOPE_COMPAT:
        kwargs["check_embedding_ctx_length"] = False
    _embeddings = OpenAIEmbeddings(**kwargs)
    return _embeddings


def _iter_knowledge_files() -> list[Path]:
    """收集 knowledge 目录下可索引的文本（.md / .txt），排除占位文件。"""
    if not KNOWLEDGE_DIR.is_dir():
        return []
    paths: list[Path] = []
    for pattern in ("**/*.md", "**/*.txt"):
        for path in KNOWLEDGE_DIR.glob(pattern):
            if path.name.startswith("."):
                continue
            if path.name == ".gitkeep":
                continue
            paths.append(path)
    return sorted(set(paths))


def load_knowledge_documents():
    """加载并返回 LangChain Document 列表。"""
    from langchain_core.documents import Document

    files = _iter_knowledge_files()
    if not files:
        return []
    docs = []
    for file_path in files:
        loader = TextLoader(str(file_path), encoding="utf-8")
        for doc in loader.load():
            # 元数据里带上相对路径，便于回答时追溯来源
            doc.metadata["source"] = str(file_path.relative_to(KNOWLEDGE_DIR))
            docs.append(doc)
    return docs


def _get_text_splitter():
    """中文友好分段。"""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["\n\n", "\n", "。", "；", " ", ""],
    )


def _filter_nonempty_chunks(chunks: list) -> list:
    """去掉空片段，保证传给 Embedding 的均为非空 str，避免兼容网关报错。"""
    out = []
    for doc in chunks:
        text = (doc.page_content or "").strip()
        if not text:
            continue
        doc.page_content = text
        out.append(doc)
    return out


def _persist_dir_ready() -> bool:
    """判断本地是否已有 Chroma 持久化数据（存在 sqlite 即认为已建库）。"""
    sqlite = CHROMA_PERSIST_DIR / "chroma.sqlite3"
    return sqlite.is_file()


def ingest_vectorstore(*, force: bool = False) -> Chroma:
    """
    从磁盘知识文件构建向量库并持久化到 data/chroma_db。
    :param force: True 时删除旧库再全量重建
    """
    global _vectorstore
    embeddings = _get_embeddings()
    if force and CHROMA_PERSIST_DIR.exists():
        shutil.rmtree(CHROMA_PERSIST_DIR)
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)

    raw_docs = load_knowledge_documents()
    if not raw_docs:
        raise FileNotFoundError(
            f"未在 {KNOWLEDGE_DIR} 找到 .md 或 .txt 知识文件，请先放入文档后再执行 ingest。"
        )

    splitter = _get_text_splitter()
    chunks = _filter_nonempty_chunks(splitter.split_documents(raw_docs))
    if not chunks:
        raise ValueError(
            "分段后没有有效文本（可能知识文件为空或仅空白）。请检查 data/knowledge 下 .md/.txt 内容。"
        )

    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_PERSIST_DIR),
        collection_name=CHROMA_COLLECTION_NAME,
    )
    return _vectorstore


def get_vectorstore(*, rebuild: bool = False) -> Chroma:
    """
    获取向量库：默认加载已有持久化；不存在则自动 ingest；rebuild=True 强制重建。
    """
    global _vectorstore
    if rebuild:
        _vectorstore = ingest_vectorstore(force=True)
        return _vectorstore

    if _vectorstore is not None:
        return _vectorstore

    embeddings = _get_embeddings()
    if _persist_dir_ready():
        _vectorstore = Chroma(
            persist_directory=str(CHROMA_PERSIST_DIR),
            embedding_function=embeddings,
            collection_name=CHROMA_COLLECTION_NAME,
        )
        return _vectorstore

    _vectorstore = ingest_vectorstore(force=False)
    return _vectorstore


def get_retriever():
    """供 RAG 链与 Tool 使用的检索器。"""
    vs = get_vectorstore()
    return vs.as_retriever(search_kwargs={"k": RAG_TOP_K})


def format_retrieved_context(docs) -> str:
    """将检索结果格式化为注入 Prompt 的纯文本。"""
    if not docs:
        return "（本轮未检索到与问题强相关的知识库片段，请依据通用医学安全原则作答，并提醒用户咨询医生。）"
    parts = []
    for i, doc in enumerate(docs, 1):
        src = doc.metadata.get("source", "unknown")
        parts.append(f"[片段{i} | 来源: {src}]\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(parts)
