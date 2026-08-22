# gateway/ — 托管 MCP 网关（M3）

把注册表里的 stdio 服务器**托管在平台侧**，以 streamable-HTTP 暴露给 agent / 任意 MCP 客户端。企业终端不需要 node / uvx / docker，凭据不落终端。

## 端点

```
POST/GET/DELETE  https://mcp.taituai.com/g/{org}/{server}/mcp      # MCP streamable-HTTP（agent server_task.py 原生支持）
GET              https://mcp.taituai.com/g/{org}/{server}/health
```

鉴权：`Authorization: Bearer <org_key>`（由 `api/` `/api/orgs/:org/keys` 签发，scope 限定可访问的 server 列表）。agent 侧配置：

```yaml
mcp_servers:
  github:
    url: https://mcp.taituai.com/g/acme/github/mcp
    headers: { Authorization: "Bearer ${MCP_GITHUB_API_KEY}" }
```

## 技术选型

Python 3.11 + FastAPI + `mcp` SDK（与 agent 同一套 SDK，`server_task.py` 的连接经验可直接复用）。

```
gateway/
  app.py              FastAPI：路由、鉴权、限流（org × server）、审计
  session_pool.py     (org, server) → 子进程会话池：懒启动、空闲回收、并发上限
  backend/stdio.py    在 docker 沙箱（--network 白名单 = 清单 security.egress）中启动 stdio 服务器
  backend/proxy.py    上游已是 http 的服务器 → 反代 + 注入 org 凭据
  vault.py            org 凭据读取（KMS / HashiCorp Vault / 最小实现：加密 Mongo 字段）
  policy.py           org 级工具 allowlist、只读模式、速率
  audit.py            每次 tools/call 记录 (org, user?, server, tool, args_hash, duration, ok)
```

## 关键约束

- 一个 (org, server) 只有一个共享会话（与 agent 的 `identity: shared` 语义一致）；需要 per-user 凭据的服务器（`identity: per-requester`）不托管，仍走本地 stdio。
- MCP `notifications/tools/list_changed` 透传，agent 端自动刷新。
- 超时：连接 30s、单次 tools/call 300s（与 agent `tool_supervisor` 的 `mcp: 300` 对齐）。
- 子进程 env 白名单与 agent `helpers.py` 同一份，只叠加 vault 注入的变量。
