# MCP 文件系统允许目录

当 `.env` 中 **`USE_MCP=true`** 时，官方 MCP **filesystem** 服务只会在此目录（或你配置的 `MCP_FILESYSTEM_ROOT`）内读写。

请将希望助理通过 MCP 读取的备忘、用药说明等 **`.txt` / `.md`** 放在本目录下，例如：`用药备忘.txt`。

**安全提示**：不要在此目录存放密钥、隐私原件；Agent 可能通过工具读取可见内容。
