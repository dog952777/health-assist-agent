# 健康助理智能体

基于 **Python + LangChain + MCP + RAG + ReAct** 的健康助理，用于学习与搭建智能体。

## 环境

- Python 3.11+（由 [mise](https://mise.jndev.com/) 管理）
- 依赖由 [Poetry](https://python-poetry.org/) 管理

## 快速开始

```bash
# 1. 安装 Python（若已安装 mise）
mise install

# 2. 安装依赖
poetry install

# 3. 配置 API Key（复制 .env.example 为 .env 并填写）
cp .env.example .env

# 4. 运行阶段1 对话（纯 LLM）
poetry run python -m src.main
# 或
poetry run doctor-agent
```

## 构建计划

详细分步见 **[BUILD_PLAN.md](./BUILD_PLAN.md)**，按阶段 0 → 1 → 2 → 3 → 4 → 5 推进。

## 架构与目录

从研发与系统分层角度的说明见 **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**。

## 项目结构

```
src/
├── main.py      # 入口
├── agent.py     # Agent / 对话链
├── prompts.py   # System Prompt
├── config.py    # 配置
└── tools/       # RAG、MCP 等工具（后续阶段）
```

## 免责声明

本助手仅作健康信息参考与生活助理，不替代医生诊断或处方，涉及用药与症状请咨询医生。
