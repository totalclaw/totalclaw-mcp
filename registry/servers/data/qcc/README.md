# 企查查

查询企业工商登记、股东结构、主要人员与经营风险等公开企业信息。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 7 个工具（只读 7 / 写入 0）。

## 工具

- `search_company`（只读）— 按关键词模糊搜索企业，返回企业名、统一社会信用代码、法定代表人与经营状态。 拿到企业名或信用代码后，再用其他工具查详情。
- `get_company_basic`（只读）— 按企业全名或统一社会信用代码查询工商基本信息（注册资本、成立日期、经营范围等）。
- `verify_company`（只读）— 校验企业信息是否真实存在，用于核验对方提供的企业名或信用代码。
- `get_shareholders`（只读）— 查询企业的股东与出资信息（股东名称、出资额、持股比例）。
- `get_key_persons`（只读）— 查询企业主要人员（董监高）的姓名与职务。
- `get_branches`（只读）— 查询企业的分支机构列表。
- `get_investments`（只读）— 查询企业的对外投资情况（投资了哪些企业、持股比例）。

## 安装

```bash
totalclaw mcp install qcc
```

## 需要的凭据

- `QCC_APP_KEY`（密钥）
- `QCC_SECRET_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://openapi.qcc.com/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
