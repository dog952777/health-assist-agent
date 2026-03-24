"""
配置集中管理：从环境变量读取 API Key、模型名等，避免硬编码。
"""
import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录下的 .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 在首次 import chromadb 之前尽量关闭遥测，避免 posthog 与 Chroma 版本不兼容（capture 参数报错）
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("POSTHOG_DISABLED", "true")


def _strip_env(name: str, default: str = "") -> str:
    """去掉首尾空格，避免 .env 里误带空格导致请求 URL 非法。"""
    value = os.getenv(name, default)
    return value.strip() if value else ""


def _normalize_openai_base_url(raw: str) -> str:
    """
    OpenAI 兼容接口的 base_url 必须以 http:// 或 https:// 开头。
    若用户只填了域名（如 api.xxx.com/v1），httpx 会报 UnsupportedProtocol。
    """
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw.rstrip("/")
    warnings.warn(
        f"环境变量 OPENAI_API_BASE 的值「{raw[:80]}…」缺少 http:// 或 https://，"
        "已忽略该配置，将使用 OpenAI 官方默认地址。请改为例如：https://api.openai.com/v1",
        UserWarning,
        stacklevel=2,
    )
    return ""


# LLM
OPENAI_API_KEY = _strip_env("OPENAI_API_KEY")
OPENAI_API_BASE = _normalize_openai_base_url(_strip_env("OPENAI_API_BASE"))


def _is_dashscope_like_base(url: str) -> bool:
    """是否为百炼 / 阿里云 DashScope 等兼容 OpenAI 的网关（用于 Embedding 特殊处理）。"""
    if not url:
        return False
    u = url.lower()
    return "dashscope" in u or "aliyuncs.com" in u


# 为 True 时，OpenAIEmbeddings 须关闭「按 token 切块传 int[]」，否则百炼报 input.contents 类型错误
OPENAI_IS_DASHSCOPE_COMPAT = _is_dashscope_like_base(OPENAI_API_BASE)

DEFAULT_LLM_MODEL = _strip_env("LLM_MODEL", "gpt-4o-mini")
# 请求超时（秒）；国内或中转较慢时可加大，例如 120
OPENAI_TIMEOUT = float(_strip_env("OPENAI_TIMEOUT", "120") or "120")

# 知识库路径（阶段2 RAG 使用）
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
# Chroma 持久化目录（本地免费向量库，勿提交到 Git）
CHROMA_PERSIST_DIR = DATA_DIR / "chroma_db"


def _resolve_embedding_model() -> str:
    """
    向量模型名须与 OPENAI_API_BASE 所在平台一致。
    百炼/DashScope 不提供 text-embedding-3-small，常用 text-embedding-v2（以控制台为准）。
    """
    raw = _strip_env("EMBEDDING_MODEL", "")
    is_dashscope_like = _is_dashscope_like_base(OPENAI_API_BASE)
    dash_default = "text-embedding-v2"
    openai_default = "text-embedding-3-small"

    if not raw:
        return dash_default if is_dashscope_like else openai_default

    # 误把 OpenAI 默认向量模型配在百炼上时，自动纠正并提示
    if is_dashscope_like and raw in (
        "text-embedding-3-small",
        "text-embedding-3-large",
        "text-embedding-ada-002",
    ):
        warnings.warn(
            f"当前 OPENAI_API_BASE 为阿里云/百炼兼容地址，向量模型「{raw}」不可用，"
            f"已自动改用「{dash_default}」。可在 .env 中显式设置 EMBEDDING_MODEL。",
            UserWarning,
            stacklevel=2,
        )
        return dash_default

    return raw


EMBEDDING_MODEL = _resolve_embedding_model()
# RAG 检索条数
try:
    RAG_TOP_K = max(1, int(_strip_env("RAG_TOP_K", "4") or "4"))
except ValueError:
    RAG_TOP_K = 4
# 是否启用 RAG（阶段2）；设为 false 则退回纯 LLM
USE_RAG = _strip_env("USE_RAG", "true").lower() in ("1", "true", "yes", "on")
# 是否使用 ReAct Agent（阶段3）：true 时由模型按需调用工具；false 时沿用阶段2「每轮先检索再生成」链
USE_REACT_AGENT = _strip_env("USE_REACT_AGENT", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# ReAct 模式下调为 true 时，chat_react 用 stream 打印每步消息变化（体验工具调用流程）
REACT_VERBOSE = _strip_env("REACT_VERBOSE", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
