# 钉钉

查询钉钉通讯录与部门，发送工作通知，查询考勤与审批实例。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 8 个工具（只读 7 / 写入 1）。

## 工具

- `list_departments`（只读）— 获取部门列表。默认从根部门开始。
- `list_department_users`（只读）— 获取部门下的成员详情列表。
- `get_user`（只读）— 获取单个成员的详细信息。
- `get_userid_by_mobile`（只读）— 通过手机号查询成员 userid。
- `send_work_notification`（**写入**）— 发送工作通知给指定成员或部门。这会真实推送通知到钉钉。
- `list_attendance_records`（只读）— 查询指定成员在某时间段内的考勤打卡结果。
- `get_approval_instance`（只读）— 查询单个审批实例的详情（申请人、表单内容、审批流程与结果）。
- `list_approval_instance_ids`（只读）— 按审批模板与时间范围查询审批实例 ID 列表。

## 安装

```bash
totalclaw mcp install dingtalk
```

## 需要的凭据

- `DINGTALK_APP_KEY`（密钥）
- `DINGTALK_APP_SECRET`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://open.dingtalk.com/document/orgapp/api-overview

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
