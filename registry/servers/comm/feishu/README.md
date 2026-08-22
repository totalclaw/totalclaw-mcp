# 飞书 / Lark

查询飞书通讯录、日历与云文档，发送消息，读写多维表格（Bitable）。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 9 个工具（只读 7 / 写入 2）。

## 工具

- `send_message`（**写入**）— 向用户、群聊发送消息。这会真实推送消息到飞书。
- `list_chats`（只读）— 获取机器人所在的群列表。
- `get_chat_messages`（只读）— 读取指定群聊的历史消息。
- `get_user_by_mobile_or_email`（只读）— 通过手机号或邮箱批量查询用户的 open_id / user_id。
- `list_department_users`（只读）— 获取部门下的用户列表。
- `list_bitable_records`（只读）— 查询多维表格（Bitable）某数据表中的记录。
- `create_bitable_record`（**写入**）— 向多维表格数据表中新增一条记录。这会写入飞书文档。
- `list_calendar_events`（只读）— 查询日历上的日程安排。
- `search_docs`（只读）— 搜索云文档（文档、表格、多维表格等）。

## 安装

```bash
totalclaw mcp install feishu
```

## 需要的凭据

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://open.feishu.cn/document/server-docs/api-call-guide/overview

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
