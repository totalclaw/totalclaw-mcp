# 百度网盘

浏览、搜索百度网盘文件与目录，查询文件详情、容量与分类文件列表。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 6 个工具（只读 6 / 写入 0）。

## 工具

- `list_files`（只读）— 列出指定目录下的文件与子目录。根目录传 "/"。
- `search_files`（只读）— 在指定目录下按关键词搜索文件，可递归搜索子目录。
- `get_file_metas`（只读）— 按文件 ID（fsid）批量查询文件详情。fsid 来自 list_files / search_files 的结果。 dlink=1 可同时取下载直链（直链有时效）。
- `list_category_files`（只读）— 按文件类型列出文件（视频、音频、图片、文档、应用、种子）。
- `get_quota`（只读）— 查询网盘的总容量与已用容量。
- `get_user_info`（只读）— 获取当前授权用户的网盘账号信息，可用于验证凭据是否有效。

## 安装

```bash
totalclaw mcp install baidu_netdisk
```

## 需要的凭据

- `BAIDU_NETDISK_ACCESS_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://pan.baidu.com/union/doc/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
