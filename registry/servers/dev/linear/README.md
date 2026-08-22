# Linear

查询和管理 Linear 的 Issue、项目、团队与周期（Cycle）。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 8 个工具（只读 6 / 写入 2）。

## 工具

- `list_issues`（只读）— 查询 Issue 列表，按更新时间倒序。可按团队、状态类型、负责人过滤。 状态类型取值：backlog / unstarted / started / completed / canceled。
- `search_issues`（只读）— 按关键词全文搜索 Issue，匹配标题与描述。
- `get_issue`（只读）— 按 Issue 标识（如 ENG-123）查询单个 Issue 的完整详情与评论。
- `list_teams`（只读）— 列出全部团队，返回 key 与名称。过滤 Issue 时要用团队 key。
- `list_projects`（只读）— 列出项目及其进度、状态与目标日期。
- `create_issue`（**写入**）— 创建一个 Issue。这会真实写入 Linear，团队成员可见。
- `comment_issue`（**写入**）— 给指定 Issue 添加一条评论。这会真实写入 Linear。
- `get_me`（只读）— 获取当前 API Key 对应的 Linear 账号与所属组织，可用于验证凭据。

## 安装

```bash
totalclaw mcp install linear
```

## 需要的凭据

- `LINEAR_API_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://developers.linear.app/docs/graphql/working-with-the-graphql-api

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
