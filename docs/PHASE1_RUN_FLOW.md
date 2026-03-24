# 阶段 1 代码运行逻辑图（纯对话：`USE_RAG=false`）

> **说明**：阶段 1 指 **不启用 RAG** 的路径：`.env` 中 `USE_RAG=false`（或与 `true` 相对的关闭值）。此时 `get_chat_chain()` 返回 **`Prompt | ChatOpenAI`**，无 Chroma、无检索。

以下流程图使用 [Mermaid](https://mermaid.js.org/) 编写；在支持 Mermaid 的 Markdown 预览中可直接渲染。

---

## 1. 总览：从启动到一轮对话

```mermaid
flowchart TD
    A["python -m src.main<br/>或 doctor-agent"] --> B{OPENAI_API_KEY<br/>已配置?}
    B -->|否| B1["stderr 提示退出<br/>sys.exit(1)"]
    B -->|是| C["get_chat_chain()"]
    C --> D{USE_RAG?}
    D -->|true| D2["阶段2路径<br/>见 PHASE2_RUN_FLOW.md"]
    D -->|false| E["阶段1：<br/>_plain_prompt | get_llm()"]
    E --> F["history = []<br/>打印欢迎语"]
    F --> G["while True 循环"]

    G --> H["input('你: ').strip()"]
    H --> I{EOF / Ctrl+C?}
    I -->|是| Z["跳出循环结束"]
    I -->|否| J{输入为空?}
    J -->|是| G
    J -->|否| K{exit / quit?}
    K -->|是| K1["打印再见<br/>break"]
    K1 --> Z
    K -->|否| L["chat(chain, user_input, history)"]

    L --> M{异常类型}
    M -->|超时类| M1["打印超时说明<br/>continue"]
    M1 --> G
    M -->|其他| M2["raise 向上抛出"]
    M -->|成功| N["print 助理回复"]
    N --> G
```

---

## 2. 阶段 1 专用：`get_chat_chain()` → 单轮 `chat()`

```mermaid
flowchart LR
    subgraph config["配置加载（进程启动时）"]
        C1["config.py<br/>load_dotenv(.env)"]
        C2["读取 OPENAI_*<br/>LLM_MODEL<br/>USE_RAG=false"]
    end

    subgraph build["构建链（main 里一次）"]
        G1["get_llm()<br/>ChatOpenAI"]
        G2["_plain_prompt()<br/>system + history + human"]
        G3["chain = G2 | G1"]
    end

    subgraph round["每一轮用户输入"]
        R1["history 元组列表<br/>→ HumanMessage / AIMessage 列表"]
        R2["chain.invoke(<br/>input, history)"]
        R3["LCEL：Prompt 渲染<br/>→ LLM HTTP 请求"]
        R4["AIMessage.content<br/>→ 新 history"]
    end

    C1 --> C2
    C2 --> G1
    G1 --> G3
    G2 --> G3
    G3 --> R1
    R1 --> R2
    R2 --> R3
    R3 --> R4
```

---

## 3. 时序图：阶段 1 单次 `invoke` 在做什么

```mermaid
sequenceDiagram
    participant U as 用户终端
    participant M as main.py
    participant A as agent.chat
    participant P as ChatPromptTemplate
    participant L as ChatOpenAI
    participant API as LLM API<br/>(OpenAI 兼容)

    U->>M: 输入一行文本
    M->>A: chat(chain, input, history)
    A->>A: 展开 history 为 Messages
    A->>P: 注入 system / history / human
    P->>L: 格式化后的消息列表
    L->>API: chat.completions
    API-->>L: 模型回复
    L-->>A: AIMessage
    A-->>M: reply, new_history
    M->>U: 打印「助理: …」
```

---

## 4. 与阶段 2 的分叉（对照）

| 条件 | `get_chat_chain()` 返回 | 多出来的步骤 |
|------|-------------------------|--------------|
| `USE_RAG=false` | `_plain_prompt \| llm` | 无 |
| `USE_RAG=true` | `RunnableLambda(检索) \| prompt \| llm` | Chroma 检索 → 注入 `context` |

---

## 5. 本地如何预览图

- **VS Code**：安装「Markdown Preview Mermaid Support」等插件后预览本文件。
- **GitHub**：将本文件推送到仓库后，在网页上打开 `.md` 即可渲染 Mermaid。
- **导出图片**：可用 [Mermaid Live Editor](https://mermaid.live/) 粘贴代码块内图表导出 PNG/SVG。

阶段 2（RAG + Chroma）专用流程图见 **[PHASE2_RUN_FLOW.md](./PHASE2_RUN_FLOW.md)**。  
阶段 3（ReAct + Tools）见 **[PHASE3_RUN_FLOW.md](./PHASE3_RUN_FLOW.md)**。
