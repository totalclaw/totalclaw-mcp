# Filesystem

受控文件系统读写 — 强制根目录沙箱,支持 list / read / write / edit / search / move。args 末 path 是允许根(可多个)。

## 安装前置

设 ``MCP_FS_ROOT=/path/to/allowed/root`` 限制可访问区。

**鉴权**：无(本地 IO)

来源：https://github.com/modelcontextprotocol/servers

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
