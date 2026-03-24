"""
入口：阶段1 纯 LLM；阶段2 固定 RAG 链；阶段3 ReAct + 工具（默认）。
"""
import sys
from typing import Iterator

from src.agent import chat, chat_react, get_chat_chain, get_react_agent
from src.config import OPENAI_API_KEY, REACT_VERBOSE, USE_RAG, USE_REACT_AGENT


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    """沿 __cause__ / __context__ 展开异常链，避免重复对象。"""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        cur = cur.__cause__ or cur.__context__


def _print_network_error_hint(exc: BaseException) -> bool:
    """
    若为超时或连接/SSL/代理类错误，打印中文说明并返回 True（主循环可 continue）。
    """
    timeout_types = frozenset(
        {"APITimeoutError", "ConnectTimeout", "ReadTimeout", "TimeoutError", "PoolTimeout"}
    )
    connection_types = frozenset(
        {
            "APIConnectionError",
            "ConnectError",
            "ReadError",
            "ProxyError",
            "SSLError",
            "CertificateError",
        }
    )
    for link in _iter_exception_chain(exc):
        name = type(link).__name__
        if name in timeout_types:
            print(
                "助理: 连接 API 超时。\n"
                "常见原因：① 国内无法直连 OpenAI，请在 .env 配置可用的 OPENAI_API_BASE（如百炼兼容地址）"
                "或给终端配置稳定代理；② 将 OPENAI_TIMEOUT 调大（如 180）。\n"
                "说明：API Key 与 base 须同属一个平台；LLM_MODEL 须该平台支持。\n"
            )
            return True
        if name in connection_types:
            print(
                "助理: 无法连上模型服务（连接或 TLS/SSL 失败）。\n"
                "若报错栈里有 http_proxy、start_tls、UNEXPECTED_EOF 等：多为 **系统/环境变量里的 HTTP(S) 代理** "
                "在 TLS 握手时断开（公司网关、不支持 CONNECT 的代理、或本机「HTTPS 解密」安全软件）。\n"
                "可尝试：① 在无代理的终端重试，或换 Clash / v2ray 等正确支持 HTTPS 隧道的代理；"
                "② 使用国内兼容接口（如百炼）并设好 OPENAI_API_BASE；"
                "③ 暂时关闭对 Python/终端的 HTTPS 扫描或排除目标域名。\n"
                "说明：Key、BASE、LLM_MODEL 三者须匹配同一服务商文档。\n"
            )
            return True
    return False


def main():
    if not OPENAI_API_KEY:
        print("请设置 OPENAI_API_KEY（可在项目根目录创建 .env 并写入）。", file=sys.stderr)
        sys.exit(1)

    use_react = USE_REACT_AGENT
    if use_react:
        mode_tip = "阶段3：ReAct + 工具（时间/计算"
        if USE_RAG:
            mode_tip += " + 知识库检索"
        mode_tip += "）"
        runner = get_react_agent()
    else:
        mode_tip = "阶段2：每轮固定 Chroma 检索" if USE_RAG else "阶段1：纯对话（USE_RAG=false）"
        try:
            runner = get_chat_chain()
        except FileNotFoundError as err:
            print(f"启动失败: {err}", file=sys.stderr)
            print(
                "请确认 data/knowledge 下已有 .md/.txt 知识文件；"
                "修改知识后可执行: poetry run python -m src.rag_ingest",
                file=sys.stderr,
            )
            sys.exit(1)

    history = []
    print(f"健康助理（{mode_tip}）. 输入 exit 或 quit 退出。\n")
    if use_react:
        # 一眼确认调试开关是否生效（.env 须放在项目根目录且改后需重启进程）
        vb = "已开启 — 每轮会先打印 ReAct 调试块再显示助理回复"
        if not REACT_VERBOSE:
            vb = "未开启 — 请在项目根目录 .env 写入 REACT_VERBOSE=true 后重新运行本程序"
        print(f"ReAct 调试日志: {vb}\n")
        print("提示：知识类问题会按需检索；问「现在几点」可用工具取本机时间。\n")

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
            if use_react:
                reply, history = chat_react(runner, user_input, history)
            else:
                reply, history = chat(runner, user_input, history)
        except Exception as exc:
            if _print_network_error_hint(exc):
                continue
            raise
        print(f"助理: {reply}\n")


if __name__ == "__main__":
    main()
