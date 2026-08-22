# 简道云

查询和填写简道云表单数据：检索记录、读取单条、查看表单字段结构、新建记录。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 6 个工具（只读 5 / 写入 1）。

## 工具

- `list_apps`（只读）— 列出当前 API Key 可访问的所有应用，返回应用 ID 与名称。先用它拿到 app_id。
- `list_forms`（只读）— 列出某个应用下的全部表单，返回表单 ID 与名称。先用它拿到 entry_id。
- `list_form_fields`（只读）— 查询表单的字段结构，返回每个字段的内部名（形如 _widget_1234567890）、 标签与类型。查数据或新建记录前必须先看它，字段名不能猜。
- `query_records`（只读）— 查询表单的多条数据，按数据 ID 升序返回。翻页方式是把上一页最后一条的 _id 作为下一次的 data_id 传入（游标翻页，不是页码）。
- `get_record`（只读）— 按数据 ID 读取单条记录的完整内容。
- `create_record`（**写入**）— 在表单中新建一条数据。这会真实写入简道云。data 的键必须是字段内部名 （先用 list_form_fields 查），值形如 {"_widget_123": {"value": "内容"}}。

## 安装

```bash
totalclaw mcp install jiandaoyun
```

## 需要的凭据

- `JIANDAOYUN_API_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://hc.jiandaoyun.com/open/11470

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
