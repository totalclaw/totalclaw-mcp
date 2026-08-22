# GitHub

在 GitHub 上查询和管理仓库、Issue、Pull Request、提交与代码搜索。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 12 个工具（只读 10 / 写入 2）。

## 工具

- `search_repositories`（只读）— 按关键词搜索 GitHub 仓库，返回名称、描述、star 数与主语言。
- `get_repository`（只读）— 获取单个仓库的详情：描述、默认分支、star/fork 数、开启的 issue 数等。
- `list_issues`（只读）— 列出仓库的 Issue。默认只返回 open 状态，按更新时间倒序。
- `get_issue`（只读）— 获取单个 Issue 的完整内容，包括正文、状态、标签与指派人。
- `create_issue`（**写入**）— 在仓库中创建一个新 Issue。这会在 GitHub 上产生公开可见的写入。
- `comment_issue`（**写入**）— 给指定 Issue 或 Pull Request 添加一条评论。
- `list_pull_requests`（只读）— 列出仓库的 Pull Request，按更新时间倒序。
- `get_pull_request`（只读）— 获取单个 PR 的详情，含变更行数、可合并状态与关联分支。
- `list_commits`（只读）— 列出仓库某分支的提交历史。
- `get_file_content`（只读）— 读取仓库中某个文件的内容（返回 base64 编码的 content 字段）。
- `search_code`（只读）— 在 GitHub 上搜索代码。需要登录态，匿名不可用。
- `get_me`（只读）— 获取当前令牌对应的 GitHub 账号信息，可用于验证凭据是否有效。

## 安装

```bash
totalclaw mcp install github
```

## 需要的凭据

- `GITHUB_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://docs.github.com/rest

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
