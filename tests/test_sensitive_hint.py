"""阶段 5：敏感词模块行为单测（不调用 LLM）。"""
from src.sensitive_hint import augment_user_message_if_needed, detect_sensitive_categories


def test_detect_empty_no_categories():
    assert detect_sensitive_categories("") == []
    assert detect_sensitive_categories("   ") == []


def test_detect_emergency_keyword():
    cats = detect_sensitive_categories("胸口疼喘不过气")
    assert "急重症或急救" in cats


def test_detect_prescription_keyword():
    cats = detect_sensitive_categories("请帮我开处方")
    assert "处方或调药" in cats


def test_augment_disabled_returns_original():
    text = "请帮我开处方"
    assert augment_user_message_if_needed(text, enabled=False) == text


def test_augment_enabled_prefixes_when_hit():
    text = "请帮我开处方"
    out = augment_user_message_if_needed(text, enabled=True)
    assert out.startswith("【系统安全提示·仅本轮】")
    assert text in out


def test_augment_enabled_no_hit_unchanged():
    text = "维生素C有什么作用"
    assert augment_user_message_if_needed(text, enabled=True) == text
