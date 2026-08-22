# Sentry

Sentry 错误监控集成 — issue 查询 / event 详情 / release / project / team / 性能 / AI Codegen 错误分析。Sentry 官方维护。

## 安装前置

在 Sentry → Settings → Auth Tokens 创建带 org:read / project:read / event:read scope 的 token。

**鉴权**：SENTRY_AUTH_TOKEN + SENTRY_ORG

来源：https://github.com/getsentry/sentry-mcp

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
