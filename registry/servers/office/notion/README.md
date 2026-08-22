# Notion

搜索、读取和管理 Notion 工作区中的页面与数据库。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 9 个工具（只读 6 / 写入 3）。

## 工具

- `search`（只读）— 在工作区内搜索页面和数据库标题。不传 query 则返回最近编辑的内容。
- `get_page`（只读）— 获取页面的属性（不含正文块，正文用 get_block_children）。
- `get_block_children`（只读）— 读取页面或块的子块，即页面正文内容。
- `query_database`（只读）— 查询数据库中的条目，支持过滤与排序。
- `get_database`（只读）— 获取数据库的结构定义（有哪些字段、字段类型）。
- `create_page`（**写入**）— 在指定数据库或父页面下创建新页面。这会写入 Notion 工作区。
- `append_blocks`（**写入**）— 向页面末尾追加内容块。这会修改 Notion 页面。
- `update_page_properties`（**写入**）— 更新页面属性，也可用于归档（设 archived=true）。
- `get_me`（只读）— 获取当前集成的 bot 信息，用于验证凭据是否有效。

## 安装

```bash
totalclaw mcp install notion
```

## 需要的凭据

- `NOTION_API_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://developers.notion.com/reference/intro

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
