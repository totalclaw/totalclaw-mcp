# 腾讯云 iOA 零信任

查询 iOA 零信任管理的终端设备、终端软件、本地账号与账号分组，排查设备在线与合规状态。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 6 个工具（只读 6 / 写入 0）。

## 工具

- `list_devices`（只读）— 查询终端设备列表，返回终端 Mid、设备名、系统、在线状态与授权状态。 group_id 与 group_ids 必须给一个；未划分管理域时 domain_instance_id 传 "1"。 os_type 必须与分组匹配。设备的 Mid 是其他工具的入参。
- `get_device_info`（只读）— 查询单台终端的运行时信息。type 决定查什么： process_list 进程列表 / network_list 网络连接 / service_list 服务列表。
- `list_device_software`（只读）— 查询某台终端上已安装的软件清单。
- `get_root_account_group`（只读）— 查询账号根分组，拿到根分组 ID 后再用 list_account_groups 逐层下钻。无需参数。
- `list_account_groups`（只读）— 查询账号分组。默认查全网根分组下的直接子组，deepin 传 1 可递归查所有子组。
- `list_local_accounts`（只读）— 查询本地账号列表，返回姓名、账户名与所属分组。

## 安装

```bash
totalclaw mcp install tencent_ioa
```

## 需要的凭据

- `TENCENTCLOUD_SECRET_ID`（密钥）
- `TENCENTCLOUD_SECRET_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://cloud.tencent.com/document/product/1092

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
