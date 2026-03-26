# 阶段 5：敏感提示、多轮历史上限、README 与评测文档

> **原理与概念**见 **[PHASE5_LEARNING.md](./PHASE5_LEARNING.md)**；**用例表**见 **[eval_examples.md](./eval_examples.md)**。

## 目标

1. 用户表述命中 **急重症 / 求诊断 / 处方或调药 / 心理危机** 等类别时，**本轮**向模型附加 **【系统安全提示…】**（见 `src/sensitive_hint.py`）。  
2. 多轮 **`history`** 超过 **`CHAT_HISTORY_MAX_TURNS`** 时自动 **丢弃最早轮次**。  
3. 根目录 **README** 与 **docs**（架构、专栏索引、评测表）与 **`.env.example`** 同步阶段 5 说明。

## 配置（`.env`）

| 变量 | 说明 | 默认 |
|------|------|------|
| **`CHAT_HISTORY_MAX_TURNS`** | 保留最近多少轮 `(用户原文, 助理回复)` | `32` |
| **`SENSITIVE_HINT_ENABLED`** | 若为 `false`，不在用户句前注入前缀（System 合规句仍生效） | `true` |

## 代码路径

1. **`src/sensitive_hint.py`**：`detect_sensitive_categories`、`augment_user_message_if_needed`。  
2. **`src/agent.py`**：`_trim_chat_history`；`chat` / `chat_react` 在调用链/图前 **截断 history**，**最后一轮 Human** 使用 `effective_input`。  
3. **`src/prompts.py`**：`SYSTEM_PROMPT` 增补 **敏感场景** 规则。  
4. **`src/main.py`**：无需改逻辑（仍累积 `history`；截断在 `agent` 内完成）。

## 验收建议

1. **敏感注入**：输入含「帮我开处方」「胸口疼喘不过气」等，在 `REACT_VERBOSE=true` 时可在消息链中看到 **Human** 以 `【系统安全提示·仅本轮】` 开头。  
2. **截断**：设 `CHAT_HISTORY_MAX_TURNS=2`，先聊 3 轮不同主题，再问「第一轮我说了什么」—— 模型应 **无法** 依赖已被丢弃的早期轮次。  
3. **单测**：`poetry run pytest tests/test_sensitive_hint.py -q`。  
4. **编译**：`poetry run python -m compileall -q src`。

## 与 BUILD_PLAN 的对应

| 条目 | 实现位置 |
|------|----------|
| 5.1 敏感话题 | `prompts.py` + `sensitive_hint.py` |
| 5.2 多轮历史 | 既有 `history` + `CHAT_HISTORY_MAX_TURNS` 截断 |
| 5.3 评估用例 | `docs/eval_examples.md` |
| 5.4 运行方式 | `README.md` + `.env.example` |
