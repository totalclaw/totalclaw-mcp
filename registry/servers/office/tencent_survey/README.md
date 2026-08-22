# 腾讯问卷

查询腾讯问卷的问卷详情与回收的答卷数据。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 2 个工具（只读 2 / 写入 0）。

## 工具

- `get_survey`（只读）— 获取问卷详情（题目结构、设置等）。 注意：腾讯问卷的开放接口是尊享版付费功能，未开通时会返回权限错误。
- `list_answers`（只读）— 获取问卷的回答列表。翻页是游标式：把上一页最后一条的答卷 ID 作为 last_answer_id 传入，不是页码。

## 安装

```bash
totalclaw mcp install tencent_survey
```

## 需要的凭据

- `TENCENT_SURVEY_ACCESS_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://wj.qq.com/docs/openapi/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
