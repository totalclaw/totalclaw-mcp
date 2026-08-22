# 天眼查

查询企业工商登记、股东出资、主要人员、对外投资、变更记录与法律诉讼等公开企业数据。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 10 个工具（只读 10 / 写入 0）。

## 工具

- `search_company`（只读）— 按关键词搜索企业，返回公司名、类型、成立日期、经营状态与统一社会信用代码。 拿到准确公司名后再用其他工具查详情。
- `get_company_baseinfo`（只读）— 查询企业工商基本信息：类型、成立日期、经营状态、注册资本、法人、统一社会信用代码等。
- `get_company_contact`（只读）— 查询企业基本信息并含联系方式（电话、邮箱、网址）。
- `verify_company`（只读）— 企业三要素验证：核对企业名称、法人、注册号/信用代码三者是否一致。
- `get_shareholders`（只读）— 查询企业股东信息：股东名、出资比例、出资金额与股东总数。
- `get_staff`（只读）— 查询企业主要人员（董事、监事、高管）的姓名与职位。
- `get_investments`（只读）— 查询企业对外投资：被投资企业、法人、投资占比与投资总数。
- `get_change_records`（只读）— 查询企业工商变更记录：变更事项与变更前后信息。
- `get_lawsuits`（只读）— 查询企业法律诉讼：案号、案件名称、案由、涉案金额、案件身份与裁判结果。
- `get_annual_report`（只读）— 查询企业年报：基本信息、股东出资、资产状况与对外投资。

## 安装

```bash
totalclaw mcp install tianyancha
```

## 需要的凭据

- `TIANYANCHA_TOKEN`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://open.tianyancha.com/

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
