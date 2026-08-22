# 网页抓取

抓取网页并抽取正文纯文本，支持批量抓取与 JSON 接口，零凭据。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 2 个工具（只读 2 / 写入 0）。

## 工具

- `fetch_url`（只读）— 抓取一个网页并返回标题与正文纯文本。JSON 接口会直接返回解析后的 JSON；非文本内容只返回元信息。拒绝访问内网地址。
- `fetch_many`（只读）— 一次抓取多个网页（最多 10 个），每个只返回较短的正文摘要，适合快速比较多个来源。单个失败不影响其余。

## 安装

```bash
totalclaw mcp install web
```

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
