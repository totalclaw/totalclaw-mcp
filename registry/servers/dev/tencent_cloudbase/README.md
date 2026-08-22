# 腾讯云 CloudBase

查询与管理腾讯云开发 CloudBase 的环境、云函数、数据库集合与静态托管。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 5 个工具（只读 5 / 写入 0）。

## 工具

- `list_environments`（只读）— 列出账号下的 CloudBase 环境，返回环境 ID、别名、状态与套餐。先用它拿 EnvId。
- `get_env_usage`（只读）— 查询环境的资源用量（存储、CDN 流量、云函数调用次数等）。
- `list_database_collections`（只读）— 列出环境内的数据库集合（表）及其文档数与索引数。
- `describe_static_store`（只读）— 查询环境的静态网站托管信息（域名、状态、存储桶）。
- `describe_env_domains`（只读）— 查询环境绑定的安全域名列表。

## 安装

```bash
totalclaw mcp install tencent_cloudbase
```

## 需要的凭据

- `TENCENTCLOUD_SECRET_ID`（密钥）
- `TENCENTCLOUD_SECRET_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://cloud.tencent.com/document/product/876

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
