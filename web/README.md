# web/ — SSR 市场站（M4）

Express 4 SSR，**复制 `totalclaw-skill-shop/server/`**（`index.js` / `render.js` / `partials.js` / `market-routes.js`）并替换数据源为 `api/`。域名 `mcp.taituai.com`，PM2 进程 `mcp-web`，与 `mcp-api` 同机部署（`ecosystem.config.cjs`）。

## 页面

| 路径 | 内容 |
|---|---|
| `/` | 精选 + 分类 + bundle（web / social / dev / media / biz）+ 搜索 |
| `/s/:name` | 详情：描述、运行时候选、`requires_env` 清单、工具列表（来自探测快照）、安全结论、版本历史 |
| `/s/:name#install` | 一键复制：`totalclaw mcp install <name>`；`recipe?target=claude|cursor|codex` JSON；企业登录后显示托管端点 |
| `/org/:org` | 企业私有目录（SSO 登录） |
| `/developer` | 上传 / 审核状态 / 统计（复用 skill-shop 开发者中心） |

## 安装命令展示模板

```bash
# TotalClaw Agent
totalclaw mcp install github --env GITHUB_PERSONAL_ACCESS_TOKEN=<your-pat> --yes

# Claude Code
claude mcp add github -- npx -y @modelcontextprotocol/server-github@2025.4.8
```
