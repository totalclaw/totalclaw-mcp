# Canva 可画

搜索与管理 Canva 设计稿，用品牌模板批量套用内容，导出为 PDF / 图片 / PPTX。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 9 个工具（只读 7 / 写入 2）。

## 工具

- `list_designs`（只读）— 搜索用户的设计稿（含共享给他）。返回标题、缩略图、编辑/查看链接与页数。 翻页用响应里的 continuation 传回 continuation 参数。
- `get_design`（只读）— 获取单个设计稿的详情：标题、页数、缩略图与编辑/查看链接。
- `list_brand_templates`（只读）— 列出企业组织内的品牌模板。套用模板（autofill）前先用它拿 brand_template_id。 需要 Canva 企业版成员身份。
- `get_brand_template_dataset`（只读）— 查询品牌模板里可填充的字段（数据集）。做 autofill 前必须先看它， data 的键名就来自这里，不能猜。
- `create_autofill_job`（**写入**）— 用品牌模板生成一张新设计稿：把 data 里的文本/图片填进模板。这会在用户 账号下创建新设计稿。异步任务，返回 job id，再用 get_autofill_job 查结果。
- `get_autofill_job`（只读）— 查询套用模板任务的状态与结果。完成后返回新建设计稿的 id 与链接。
- `create_export_job`（**写入**）— 把设计稿导出为文件。异步任务，返回 job id，再用 get_export_job 取下载链接。 format 形如 {"type":"pdf","size":"a4"} 或 {"type":"png","width":1200}； jpg 必须带 quality(1-100)，mp4 必须带 quality(如 horizontal_1080p)。
- `get_export_job`（只读）— 查询导出任务状态。完成后返回可下载的文件 URL（有时效）。
- `get_me`（只读）— 获取当前令牌对应的 Canva 用户与团队信息，可用于验证凭据是否有效。

## 安装

```bash
totalclaw mcp install canva
```

## 需要的凭据

- `CANVA_ACCESS_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://www.canva.dev/docs/connect/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
