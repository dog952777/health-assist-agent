"""
将 data/knowledge 下的文档写入本地 Chroma。修改知识文件后请重新执行本模块。

用法：
  poetry run python -m src.rag_ingest
"""
import sys

from src.config import OPENAI_API_KEY
from src.rag import clear_vectorstore_cache, ingest_vectorstore


def main() -> None:
    if not OPENAI_API_KEY:
        print("请先在 .env 中配置 OPENAI_API_KEY（向量化需要调用 Embedding API）。", file=sys.stderr)
        sys.exit(1)
    try:
        ingest_vectorstore(force=True)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"写入向量库失败: {e}", file=sys.stderr)
        sys.exit(1)
    clear_vectorstore_cache()
    print("已向量化并写入本地 Chroma（data/chroma_db）。可运行 poetry run python -m src.main 对话。")


if __name__ == "__main__":
    main()
