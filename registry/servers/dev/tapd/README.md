# TAPD

查询和管理 TAPD 的需求、缺陷、任务与迭代，跟踪研发进度。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 9 个工具（只读 7 / 写入 2）。

## 工具

- `list_stories`（只读）— 查询需求列表，按条件批量检索。返回的每项形如 {"Story": {...}}。 默认每页 30 条，最多 200。
- `get_story`（只读）— 按需求 ID 查询单个需求的详情。
- `count_stories`（只读）— 统计满足条件的需求数量，用于快速了解规模而不拉全量数据。
- `list_bugs`（只读）— 查询缺陷列表。返回的每项形如 {"Bug": {...}}。
- `count_bugs`（只读）— 统计满足条件的缺陷数量。
- `list_tasks`（只读）— 查询任务列表。返回的每项形如 {"Task": {...}}。
- `list_iterations`（只读）— 查询迭代列表，用于了解项目的迭代规划与起止时间。
- `create_story`（**写入**）— 在项目中创建一条需求。这会真实写入 TAPD。
- `create_bug`（**写入**）— 在项目中提交一个缺陷。这会真实写入 TAPD。

## 安装

```bash
totalclaw mcp install tapd
```

## 需要的凭据

- `TAPD_API_PASSWORD`（密钥）
- `TAPD_API_USER`

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://open.tapd.cn/document/api-doc/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
