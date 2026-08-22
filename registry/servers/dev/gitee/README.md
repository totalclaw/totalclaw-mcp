# Gitee 码云

查询和管理 Gitee 仓库、Issue、Pull Request 与文件内容。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 8 个工具（只读 7 / 写入 1）。

## 工具

- `get_repository`（只读）— 获取仓库详情：描述、默认分支、star/fork 数、可见性。
- `list_user_repos`（只读）— 列出当前授权用户的仓库。
- `list_issues`（只读）— 列出仓库 Issue，可按状态过滤。
- `create_issue`（**写入**）— 在仓库中创建 Issue。这会产生对仓库可见的写入。
- `list_pull_requests`（只读）— 列出仓库的 Pull Request。
- `get_file_content`（只读）— 读取仓库中某个文件的内容（content 字段为 base64）。
- `list_commits`（只读）— 列出仓库提交历史。
- `get_me`（只读）— 获取当前令牌对应的 Gitee 账号信息，用于验证凭据。

## 安装

```bash
totalclaw mcp install gitee
```

## 需要的凭据

- `GITEE_ACCESS_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://gitee.com/api/v5/swagger

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
