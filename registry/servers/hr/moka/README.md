# Moka 招聘

查询 Moka 招聘系统的职位、候选人投递记录与组织架构，跟踪招聘进展。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 3 个工具（只读 3 / 写入 0）。

## 工具

- `list_jobs`（只读）— 查询职位列表。hireMode 必填：social 社招 / campus 校招。 返回职位名、薪资区间、经验要求、部门与工作地。
- `list_applications`（只读）— 查询候选人投递记录，返回投递 ID、来源渠道、当前阶段、职位 ID 与更新时间。 翻页用游标：首次传 fromTime，之后把响应里的 next 传回 next 参数（两者不能同时传）。
- `list_departments`（只读）— 查询完整组织架构，返回部门编码、名称与层级关系。无需参数。

## 安装

```bash
totalclaw mcp install moka
```

## 需要的凭据

- `MOKA_API_SECRET`（密钥）
- `MOKA_API_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://mokahr.moyincloud.com/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
