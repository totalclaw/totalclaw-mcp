# 腾讯云 EdgeOne

查询与管理 EdgeOne 站点、加速域名，提交刷新与预热任务。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 6 个工具（只读 4 / 写入 2）。

## 工具

- `list_zones`（只读）— 查询 EdgeOne 站点列表，返回站点 ID、域名、状态、区域与加速开关。 先用它拿 ZoneId，其他工具都要用。
- `list_acceleration_domains`（只读）— 查询站点下的加速域名及其源站配置与状态。
- `list_purge_tasks`（只读）— 查询缓存刷新任务的历史与状态。
- `list_prefetch_tasks`（只读）— 查询缓存预热任务的历史与状态。
- `create_purge_task`（**写入**）— 提交缓存刷新任务。这会真实清除线上缓存，被刷新的资源下次访问将回源， 短时间内源站压力上升。
- `create_prefetch_task`（**写入**）— 提交缓存预热任务，把指定 URL 提前拉到边缘节点。这会产生回源流量。

## 安装

```bash
totalclaw mcp install tencent_edgeone
```

## 需要的凭据

- `TENCENTCLOUD_SECRET_ID`（密钥）
- `TENCENTCLOUD_SECRET_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://cloud.tencent.com/document/product/1552/80731

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
