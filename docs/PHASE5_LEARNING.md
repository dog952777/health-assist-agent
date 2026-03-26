# 阶段 5 新手向：敏感提示、多轮历史与文档收口

> **操作与验收**见 **[PHASE5_RUN_FLOW.md](./PHASE5_RUN_FLOW.md)**；构建计划 **[BUILD_PLAN.md](../BUILD_PLAN.md)** 阶段 5；评测清单 **[eval_examples.md](./eval_examples.md)**。

---

## 1. 本阶段在解决什么问题？

| 主题 | 问题 | 做法 |
|------|------|------|
| **合规与安全** | 用户若谈急诊、求诊断、求处方等，模型容易「答得太像医生」 | **System Prompt** 长期约束 + **本轮**对用户句**可选注入**安全前缀（`src/sensitive_hint.py`） |
| **上下文窗口** | 多轮对话无限增长会撑爆 token、变慢、丢早期指令 | **`CHAT_HISTORY_MAX_TURNS`**：只保留最近 N 轮 `(用户, 助理)` |
| **可维护性** | 行为散落在多处难以回归 | **README**、**eval_examples**、架构文档与专栏索引一并更新 |

**Why 注入放在 Human 前缀而不是改历史展示？**  
历史里若长期保存带前缀的句子，下一轮会重复堆叠「系统安全提示」，浪费 token 且干扰语义；因此 **内存中的 `history` 仅存用户原文**，仅 **当前轮** 送给模型的 `HumanMessage` 使用增强后的文本。

---

## 2. 敏感检测：规则边界

- 当前实现是 **关键词/短语命中** → **提示增强**，不是拦截用户、也不是法律意义上的「内容审核产品」。  
- 误判：**正常句子里含「处方」「急诊」等子串** 可能触发；可通过调 `_TRIGGER_GROUPS` 或关闭 `SENSITIVE_HINT_ENABLED` 权衡。  
- **模型仍须**遵守 `SYSTEM_PROMPT`；注入是额外强调，不替代人工审核与产品合规流程。

---

## 3. 多轮历史截断

- **`CHAT_HISTORY_MAX_TURNS`**：对 **list[tuple]** 形式的 `history` 做 **切片保留末尾**（见 `agent._trim_chat_history`）。  
- **与 LangGraph Checkpointer 的区别**：本项目 CLI 仍用 **进程内列表**；若将来要跨会话持久化，可再接入 checkpointer，截断策略仍可复用「只取最近 N 轮」。

---

## 4. 代码对照

| 能力 | 文件 |
|------|------|
| 关键词组与注入 | `src/sensitive_hint.py` |
| 截断 + 调用注入 | `src/agent.py` → `chat` / `chat_react` |
| 环境变量 | `src/config.py` → `CHAT_HISTORY_MAX_TURNS`、`SENSITIVE_HINT_ENABLED` |
| 长期人设与免责 | `src/prompts.py` → `SYSTEM_PROMPT` |

---

## 5. 自测问题（概念）

1. 关闭 `SENSITIVE_HINT_ENABLED` 后，**System** 里的合规句是否仍在？  
2. 将 `CHAT_HISTORY_MAX_TURNS` 设为 `2`，连续聊 5 轮，早期话题是否会被「遗忘」？（预期：会，属设计行为。）  
3. `eval_examples.md` 中 #4、#12、#14 类用例是否仍为 **就医/不处方/不编造**？
