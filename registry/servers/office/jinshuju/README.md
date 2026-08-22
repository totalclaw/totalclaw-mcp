# 金数据

查询金数据的表单、字段结构与提交数据，用于汇总问卷、报名与收款记录。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 4 个工具（只读 4 / 写入 0）。

## 工具

- `list_forms`（只读）— 列出账号下的全部表单，返回表单标识（form_token）与名称。先用它拿到 form_token。
- `get_form`（只读）— 查询单个表单的详情与字段结构。返回的字段标识形如 field_1、field_2， 查数据或做筛选前必须先看它，字段名不能猜。
- `list_entries`（只读）— 查询表单的提交数据。翻页用游标（响应的 Link 头里带 cursor）， 也可按字段值过滤 —— 字段名用 field_1 这种标识，先用 get_form 查。
- `get_entry`（只读）— 按序号读取单条提交数据的完整内容。

## 安装

```bash
totalclaw mcp install jinshuju
```

## 需要的凭据

- `JINSHUJU_ACCESS_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://github.com/jinshuju/jinshuju-api-docs

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
