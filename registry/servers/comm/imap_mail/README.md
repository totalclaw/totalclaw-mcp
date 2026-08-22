# 邮箱（IMAP/SMTP）

收发、搜索和整理邮件，支持 QQ 邮箱、网易邮箱及任意 IMAP 邮箱。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 4 个工具（只读 3 / 写入 1）。

## 工具

- `list_folders`（只读）— 列出邮箱中的所有邮件夹（收件箱、已发送、垃圾邮件等）。
- `search_emails`（只读）— 搜索邮件，返回摘要列表（不含正文），按时间从新到旧。可按发件人、主题、关键词、未读状态和最近天数过滤。
- `read_email`（只读）— 读取单封邮件的完整内容，含正文与附件清单。uid 来自 search_emails。
- `send_email`（**写入**）— 发送一封纯文本邮件。这会真实投递邮件给收件人，发出后无法撤回。

## 安装

```bash
totalclaw mcp install imap_mail
```

## 需要的凭据

- `MAIL_IMAP_HOST`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
