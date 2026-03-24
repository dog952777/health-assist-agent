"""
阶段 3：与 RAG 并列的简单工具（当前时间、安全算术），供 ReAct Agent 按需调用。
"""
from __future__ import annotations

import ast
import operator
from datetime import datetime

from langchain_core.tools import tool

_BIN_OPS: dict[type[ast.operator], type] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def _eval_ast_num(node: ast.AST) -> float:
    """递归计算仅含数字与基本运算符的 AST 节点。"""
    if isinstance(node, ast.Constant):
        # bool 是 int 的子类，须先排除，避免 True/False 被当成 1/0
        if isinstance(node.value, bool):
            raise ValueError("仅支持数字常量")
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("仅支持数字常量")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_ast_num(node.operand)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _eval_ast_num(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_ast_num(node.left)
        right = _eval_ast_num(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("除数不能为 0")
        return float(_BIN_OPS[type(node.op)](left, right))
    raise ValueError("表达式含不允许的语法（仅支持 + - * / % 与括号）")


def _safe_arithmetic(expression: str) -> float:
    """解析并计算形如「(1+2)*3」的纯算术表达式。"""
    raw = (expression or "").strip()
    if not raw:
        raise ValueError("表达式为空")
    # mode="eval" 时根节点为 ast.Expression，真正的算术子树在 .body
    tree = ast.parse(raw, mode="eval")
    if not isinstance(tree, ast.Expression):
        raise ValueError("无效的表达式")
    return _eval_ast_num(tree.body)


@tool
def get_current_datetime() -> str:
    """
    返回当前本机日期与时间（ISO 格式），用于回答「现在几点」「今天星期几」等与时间相关的问题。
    不涉及用户所在时区推断时，默认使用服务器/本机本地时间。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


@tool
def calculator(expression: str) -> str:
    """
    计算仅含数字与运算符的算术表达式（支持 +、-、*、/、%、** 与括号）。
    用于用药频次换算、剂量简单加减等；复杂医学计算应提醒用户咨询医生或药师。
    """
    try:
        value = _safe_arithmetic(expression)
        if value == int(value):
            return str(int(value))
        return str(value)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError) as exc:
        return f"无法计算：{exc}。请只使用数字与 + - * / % 和括号。"
