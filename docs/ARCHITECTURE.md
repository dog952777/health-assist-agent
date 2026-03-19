# 健康助理智能体 — 架构与目录说明

本文从 **研发协作** 与 **系统架构** 两个角度说明仓库结构、职责边界与演进方向。

---

## 一、目录树（业务相关，不含 `.venv`）

```
AI/
├── .env                    # 本地密钥与运行参数（勿提交版本库）
├── .env.example            # 环境变量模板与说明（可提交）
├── .gitignore              # 忽略 .env、虚拟环境、缓存等
├── .mise.toml              # mise 指定 Python 版本（可选）
├── pyproject.toml          # Poetry 依赖、包名、入口脚本
├── poetry.lock             # 锁定依赖版本
├── README.md               # 快速开始与项目说明
├── BUILD_PLAN.md           # 分阶段搭建计划（RAG / Agent / MCP）
├── src/                    # 应用代码
│   ├── __init__.py         # 将 src 声明为 Python 包
│   ├── main.py             # CLI 入口、对话循环、错误提示
│   ├── agent.py            # LLM 实例、对话链（LCEL）
│   ├── config.py           # 读取 .env、路径、超时、Base URL 校验等
│   ├── prompts.py          # System Prompt（人设与合规边界）
│   └── tools/              # 预留：RAG Tool、MCP 转 LangChain Tools 等
│       └── __init__.py
├── data/
│   └── knowledge/          # 预留：RAG 原始文档（PDF/TXT/MD 等）
└── docs/
    ├── ARCHITECTURE.md     # 本文档
    └── eval_examples.md    # 预留：评测用例与预期行为
```

---

## 二、研发视角：文件职责与协作

| 文件/目录 | 研发上怎么用 |
|-----------|----------------|
| **`pyproject.toml` + `poetry.lock`** | 定义依赖与脚本；升级 LangChain / 向量库等在此修改，`poetry lock` 后提交 lock。 |
| **`.env` / `.env.example`** | 每人本地 `.env` 存放密钥；`.env.example` 仅变量名与注释，新人复制后填写。 |
| **`src/config.py`** | **配置单一入口**：集中读取环境变量、校验 `OPENAI_API_BASE`、超时等；切换厂商（百炼 / OpenAI）优先改环境变量。 |
| **`src/prompts.py`** | **提示词迭代**：人设、免责、工具使用说明等集中维护，避免与编排逻辑混杂。 |
| **`src/agent.py`** | **智能体核心**：当前组装 `ChatOpenAI` + Prompt；后续在此接入 **Tools、ReAct / LangGraph**。 |
| **`src/main.py`** | **交付入口**：现为 CLI；若增加 Web/API，可新增模块或改入口，复用 `agent.chat` 等能力。 |
| **`src/tools/`** | **能力扩展点**：RAG 检索、MCP 工具等按模块拆分，便于单测与复用。 |
| **`data/knowledge/`** | **RAG 语料**：仅放置合规、有权限使用的文档；索引与向量库路径建议由 `rag` 或 `tools` 层管理。 |
| **`docs/eval_examples.md`** | **回归清单**：变更 Prompt 或模型后按表抽检，防止行为漂移。 |
| **`BUILD_PLAN.md`** | **路线图**：与里程碑对齐，便于分工（RAG / MCP / 评测）。 |

**日常开发流**：修改代码 → `poetry run python -m src.main` 或 `poetry run doctor-agent` → 按需补充 `tests/`（可选）。

---

## 三、架构视角：分层与数据流

### 3.1 当前实现（阶段 1：纯对话）

```
[用户终端]
    ↓ 文本输入
main.py          ← 表现层 / 适配器（CLI）
    ↓ 调用 chat()
agent.py         ← 应用层：编排（LCEL 链）
    ├─ prompts.py    ← 策略：System 人设与边界
    ├─ config.py     ← 配置
    └─ ChatOpenAI → 外部 LLM（OpenAI 兼容，如百炼 DashScope）
    ↓
[模型服务] HTTPS API
```

- **表现层**：`main.py`（未来可替换为 HTTP / Web UI）。  
- **应用 / 领域层**：`agent.py` + `prompts.py`。  
- **基础设施层**：`config.py` + 远端 LLM。  
- **横切**：网络超时等在 `main.py` 对用户给出可操作提示。

### 3.2 规划演进（与 BUILD_PLAN 一致）

```
用户
  → main（入口）
  → Agent（ReAct / LangGraph：推理与选工具）
        ├─ Tool: RAG（data/knowledge → 向量检索）
        ├─ Tool: 本地工具（时间、计算等）
        └─ Tool: MCP 暴露的外部能力（日历、文件等）
  → LLM（可继续通过 OpenAI 兼容接口接百炼等）
```

设计原则：**入口薄、Agent 负责决策与编排、Tools 插件化、密钥与配置外置**。

---

## 四、`src/__init__.py` 说明

将 `src` 标记为 Python **包**，保证 `import src.xxx`、`python -m src.main` 与 Poetry 包安装行为一致；当前无业务逻辑，可按需在包级导出公共 API 或 `__version__`。

---

## 五、相关文档

- [BUILD_PLAN.md](../BUILD_PLAN.md) — 分阶段实施计划  
- [README.md](../README.md) — 环境与运行命令  
- [eval_examples.md](./eval_examples.md) — 评测示例表  

---

*文档随代码演进更新；重大结构调整时请同步修改本节。*
