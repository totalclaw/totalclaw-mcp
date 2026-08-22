# 企业微信

查询企业微信通讯录、部门与成员，发送应用消息，管理外部联系人。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 8 个工具（只读 6 / 写入 2）。

## 工具

- `list_departments`（只读）— 获取部门列表。不传 department_id 则返回全部部门。
- `list_department_users`（只读）— 获取部门成员的详细信息（姓名、职位、手机、邮箱等）。
- `get_user`（只读）— 获取单个成员的详细信息。
- `send_text_message`（**写入**）— 向指定成员、部门或标签发送应用文本消息。这会真实推送消息给企业成员。
- `send_markdown_message`（**写入**）— 发送 Markdown 格式的应用消息（仅企业微信客户端可见渲染效果）。
- `list_external_contacts`（只读）— 获取指定成员名下的外部联系人 UserID 列表（需要客户联系权限）。
- `get_external_contact`（只读）— 获取外部联系人的详情（昵称、企业、添加时间、跟进人）。
- `get_user_id_by_mobile`（只读）— 通过手机号查询企业成员的 UserID。

## 安装

```bash
totalclaw mcp install wecom
```

## 需要的凭据

- `WECOM_CORP_ID`
- `WECOM_SECRET`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://developer.work.weixin.qq.com/document/path/90664

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
