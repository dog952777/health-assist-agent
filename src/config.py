"""
配置集中管理：从环境变量读取 API Key、模型名等，避免硬编码。
"""
import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录下的 .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


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
DEFAULT_LLM_MODEL = _strip_env("LLM_MODEL", "gpt-4o-mini")
# 请求超时（秒）；国内或中转较慢时可加大，例如 120
OPENAI_TIMEOUT = float(_strip_env("OPENAI_TIMEOUT", "120") or "120")

# 知识库路径（阶段2 RAG 使用）
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
