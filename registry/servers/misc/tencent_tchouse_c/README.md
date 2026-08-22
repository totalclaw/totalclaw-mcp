# 腾讯云数据仓库 TCHouse-C

查询 TCHouse-C（ClickHouse）实例、节点、分片与逻辑集群，以及库表元数据和备份任务。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 9 个工具（只读 9 / 写入 0）。

## 工具

- `list_instances`（只读）— 列出账号下的 TCHouse-C 实例，返回实例 ID、名称、状态、规格与地域。 先用它拿 InstanceId，其余工具都要用。
- `get_instance`（只读）— 查询单个实例的详细信息（规格、版本、网络、计费方式、到期时间）。
- `get_instance_state`（只读）— 查询实例当前状态与正在执行的操作进度。排查“实例卡在某个操作”时先看这个： 返回状态、流程名、进度百分比与错误信息。
- `list_instance_clusters`（只读）— 查询实例下的逻辑集群（vcluster）列表。
- `list_instance_nodes`（只读）— 查询实例的节点列表，返回节点 IP、规格、角色与状态。
- `get_instance_shards`（只读）— 查询实例的 shard 分片信息。
- `query_metadata`（只读）— 查询 ClickHouse 元数据。api_type 决定查什么： GetClusters 逻辑集群列表 / GetSystemUsers 系统用户 / GetClusterDatabases 库列表 / GetClusterTables 表列表 / GetPrivilegeUsers 授权用户。 查库表和用户时必须同时传 cluster（逻辑集群名，可用 GetClusters 先取）。
- `list_backup_jobs`（只读）— 查询实例的备份任务列表与执行状态。
- `list_specs`（只读）— 查询指定可用区可购买的节点规格与云盘选项，用于扩容前的规格选型。

## 安装

```bash
totalclaw mcp install tencent_tchouse_c
```

## 需要的凭据

- `TENCENTCLOUD_SECRET_ID`（密钥）
- `TENCENTCLOUD_SECRET_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://cloud.tencent.com/document/product/1299

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
