# GitHub

GitHub REST API 集成 — 仓库 / issue / PR / commit / search / release / branch / fork。对 LLM 暴露 ~30 个 gh 工具。已归档但仍可用;Composio 内置同等能力,优先用 composio。

## 安装前置

在 https://github.com/settings/tokens 建 PAT(repo + workflow + read:org scope),设 ``GITHUB_PERSONAL_ACCESS_TOKEN``。

**鉴权**：GITHUB_PERSONAL_ACCESS_TOKEN

来源：https://github.com/modelcontextprotocol/servers-archived

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
