"""
阶段 5：敏感场景检测（关键词/短语），向本轮用户消息注入额外安全约束。
说明：这是「提示增强」而非内容审核拦截；不替代模型判断与人工审核。
"""
from __future__ import annotations

# (日志/提示用标签, 关键词子串)；命中即加入本轮注入前缀
_TRIGGER_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("急重症或急救", ("急诊", "急救", "120", "吐血", "呕血", "昏迷", "抽搐", "喘不过气", "窒息", "心梗", "心绞痛", "中风", "高热不退", "意识不清")),
    ("求诊断或自我定性", ("确诊", "我是不是得了", "是不是癌", "什么病", "帮我诊断", "算一下什么病", "严重吗")),
    ("处方或调药", ("处方", "开药", "帮我开", "剂量改", "加量", "停药", "换药", "处方签", "一天吃几片")),
    ("心理危机表述", ("自杀", "自残", "不想活")),
)

# 本轮注入在 Human 消息前；模型仍须遵守 SYSTEM 中的长期合规要求
_INJECTION_TEMPLATE = (
    "【系统安全提示·仅本轮】用户表述可能涉及：{categories}。"
    "请务必：① 不代替医生给出诊断或处方，不擅自给出具体用药剂量/停药建议；"
    "② 若疑似急重症，明确建议立即拨打 120 或前往急诊；"
    "③ 其余情况反复强调咨询正规医院医生或药师；④ 知识库与工具不足时不得编造医学结论。\n\n"
)


def detect_sensitive_categories(user_text: str) -> list[str]:
    """返回命中的敏感类别标签列表（有序、去重）。"""
    if not user_text or not user_text.strip():
        return []
    text = user_text.strip()
    seen: set[str] = set()
    out: list[str] = []
    for label, keywords in _TRIGGER_GROUPS:
        if any(kw in text for kw in keywords):
            if label not in seen:
                seen.add(label)
                out.append(label)
    return out


def augment_user_message_if_needed(user_text: str, enabled: bool) -> str:
    """
    若开启且命中敏感类别，在用户原文前附加一段安全提示，供本轮 LLM 阅读。
    历史记录中仍保存用户「原文」（不含本前缀），避免污染多轮展示。
    """
    if not enabled:
        return user_text
    cats = detect_sensitive_categories(user_text)
    if not cats:
        return user_text
    return _INJECTION_TEMPLATE.format(categories="、".join(cats)) + user_text
