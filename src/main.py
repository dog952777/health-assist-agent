"""
入口：阶段1 为简单 CLI 对话；后续可改为 Gradle/FastAPI 等。
"""
import sys

from src.agent import get_chat_chain, chat
from src.config import OPENAI_API_KEY


def main():
    if not OPENAI_API_KEY:
        print("请设置 OPENAI_API_KEY（可在项目根目录创建 .env 并写入）。", file=sys.stderr)
        sys.exit(1)
    chain = get_chat_chain()
    history = []
    print("健康助理（阶段1：纯对话）. 输入 exit 或 quit 退出。\n")
    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("再见。")
            break
        try:
            reply, history = chat(chain, user_input, history)
        except Exception as exc:
            # 网络/超时类错误给出可操作提示，避免整段 Traceback 吓到人
            name = type(exc).__name__
            if name in ("APITimeoutError", "ConnectTimeout", "ReadTimeout", "TimeoutError"):
                print(
                    "助理: 连接 API 超时。\n"
                    "常见原因：① 国内网络无法直连 OpenAI，需在 .env 配置可用的 OPENAI_API_BASE（中转）"
                    "或给系统/终端配置代理；② 把 OPENAI_TIMEOUT 调大（如 180）。\n"
                    "说明：API Key 属于「哪个平台」要看你从哪复制的 key；"
                    "模型名由 LLM_MODEL 决定，需与该平台上支持的模型一致。\n"
                )
                continue
            raise
        print(f"助理: {reply}\n")


if __name__ == "__main__":
    main()
