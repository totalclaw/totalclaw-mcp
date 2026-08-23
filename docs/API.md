# 接口合约

三层：① 平台 `api/`（公网，M2）② agent `qiye_api`（本机 127.0.0.1:<port>，qiye-app 唯一入口，M1）③ agent CLI（M1）。
M1 阶段 ① 的平台服务可以不存在——agent 直接拉 Gitee raw 的 `registry.json`；
需要分页/多语言/逐条下载时，用本仓已实现的 **⓪ 读接口**（`api/server`，FastAPI，
就地读仓库、无数据库），形状与 ① 一致，M2 平台接管时前端不用改。

---

## ⓪ 本仓读接口（`api/server`，FastAPI，**已实现**）

就地读 `registry.json` 与 `registry/servers/**`，没有数据库。跑法与说明见
[`api/README.md`](../api/README.md)。默认端口 3101，Swagger `/api/docs`，全部只读、免鉴权。

```
GET /healthz                                  → { ok, servers }
GET /registry.json                            # 与磁盘逐字节一致
```

### 分页查询（多语言）

```
GET /api/mcp/servers
    ?q=&category=&transport=stdio|http&launcher=npx|uvx|docker&tag=
    &verified=true|false&no_credentials=true|false
    &page=1&page_size=24&lang=zh-CN|en
→ {
  items: [RegistryEntry & {
    display_name_localized: string,      // 本语言 → 另一语言 → slug
    description_localized: string,
    category_label: string,              // 分类的本语言展示名
    lang: string
  }],
  total, page, page_size, total_pages, lang
}
```

- `page_size` ∈ [1,100]，超上限 **422**（不静默截断）。
- `page` 越界**夹到最后一页**，不返回空列表——返回空前端只会以为目录空了。
- `q` 一次搜中英文名 + 中英文描述 + 标签 + 工具名（输入语言与界面语言无关）。
- `no_credentials=true` → 只看 `requires_env` 为空、装完不用填凭据的条目。
- `lang` 不传则按 `Accept-Language` 协商（取第一段），认不出来回落 `zh-CN`。

```
GET /api/mcp/categories?lang=en               → { items: [{category, label, count}], lang }
```

### 详情

```
GET /api/mcp/servers/{name}?lang=              # name = 短名 或 totalclaw-mcp/<cat>/<name>
→ RegistryEntry & { display_name_localized, description_localized, category_label,
                    manifest: <mcp.yaml 全文>, tools_detail: [...], readme_md }
```

### 逐条目下载

```
GET /api/mcp/servers/{name}/files
→ { name, files: [{path, sha256, size}], bundle_sha256 }

GET /api/mcp/servers/{name}/files/{path}      # 单个文件原文
GET /api/mcp/servers/{name}/download          # 整条目 tar.gz
   ← ETag: "<压缩包 sha256>"
     X-Archive-Sha256: <压缩包 sha256>
     X-Bundle-Sha256:  <索引里的 bundle_sha256>
```

两个摘要别搞混：`bundle_sha256` 是**文件清单**的摘要（`sha256("<path>:<sha256>\n" …)`，
见 SPEC §分发），不是压缩包的摘要；客户端按 `files[]` 逐条校验。
打包时 mtime 与属主归零，同内容打出同字节，所以 ETag 稳定、可缓存；包内统一一层同名
目录（`awesun/mcp.yaml`）。

`{name}` 在 `/files` 与 `/download` 上只认短名（`name` 全库唯一，SPEC §1 有保证）；
`{path}` 走 `safe_join`，`../`、绝对路径、软链外指一律 400/404。

---

## ① 平台 API（`https://mcp.taituai.com`，NestJS，全局前缀 `/api`）

鉴权与 skill-shop 相同：`Authorization: Bearer <JWT>` 或 `.taituai.com` 域 `tc_token` cookie，与 totalclaw-web 共享 `JWT_SECRET`。公开读接口无需登录。

### 静态快照

```
GET /registry.json            Cache-Control: public, max-age=300
GET /registry.json.sig        Ed25519 签名（见 totalclaw-plugins/SPEC.md §8）
```

### 搜索 / 详情

```
GET /api/mcp/servers?q=&category=&transport=stdio|http&launcher=npx|uvx|docker&verified=true
                    &sort=latest|downloads|rating&page=1&pageSize=24
→ { items: [RegistryEntry], total, page, pageSize, totalPages }

GET /api/mcp/servers/:id                      # id = totalclaw-mcp/<cat>/<name> 或短名
→ RegistryEntry & { manifest: <mcp.yaml 全文对象>, tools: [{name, description, read_only, input_schema}],
                    readme_md, versions: [{version, published_at}] }

GET /api/mcp/servers/:id/recipe?target=totalclaw|claude|cursor|codex&runtime=npx
→ target=totalclaw: { mcp_servers: { <name>: {...} }, env_template: {MCP_X_Y: ""} }
  target=claude:    { mcpServers: { <name>: {command,args,env} } }

GET /api/mcp/servers/:id/files/*path          # 等价 raw_base，用于非 Gitee 环境
GET /api/mcp/categories                       # [{category, count}]
GET /api/mcp/bundles                          # {web:[...], social:[...], dev:[...], media:[...], biz:[...]}
```

### 遥测

```
POST /api/mcp/servers/:id/events
{ event: "install"|"probe_ok"|"probe_fail"|"uninstall"|"update", agent_version, os, runtime, error_class? }
→ { ok: true }      # 匿名，可用 TOTALCLAW_MCP_TELEMETRY=0 关闭
```

### 企业私有注册表（JWT，org 角色）

```
GET    /api/orgs/:org/mcp/servers             # 私有条目 + 公共条目的 org 覆盖（如托管端点）
POST   /api/orgs/:org/mcp/servers             # 上传私有 mcp.yaml（multipart 或 {manifest, files})
DELETE /api/orgs/:org/mcp/servers/:name
GET    /api/orgs/:org/keys                    # 托管网关密钥（M3）
POST   /api/orgs/:org/keys                    # 签发 {key_id, token(一次性显示), scopes:[server...]}
```

### 开发者 / 管理员（复用 skill-shop 流程）

```
POST /api/developer/mcp           { manifest, files } → reviewStatus=pending
GET  /api/developer/mcp
GET  /api/admin/reviews/pending
POST /api/admin/reviews/:id       { action: approve|reject, note?, verified?: bool }
POST /api/admin/mcp/:id/featured  { featured: bool }
```

### RegistryEntry（`registry.json` 中 `servers[]` 元素）

```ts
interface RegistryEntry {
  name: string; id: string; display_name: string; description: string; description_zh?: string;
  version: string; author: string; license?: string; homepage?: string;
  verified: boolean; tested_with?: string; category: string; tags: string[];
  transports: ('stdio'|'http')[]; launchers: string[];
  runtimes: { id: string; type: 'stdio'|'http'; launcher?: string; auth?: string; hosted?: boolean }[];
  requires_env: { name: string; description?: string; prompt?: string; secret?: boolean; required?: boolean; runtimes?: string[] }[];
  tools_count: number; tools: string[];
  security: { scan_verdict: 'allow'|'warn'|'ask'|'block' };
  path: string; raw_base: string; git_sparse: { repo: string; subdir: string };
  files: { path: string; sha256: string; size: number }[]; bundle_sha256: string;
  stats?: { downloads: number; installs: number; ratingAvg: number };
}
```

---

## ② agent `qiye_api`（新增 `totalclaw_qiye_api/mcp_hub_api.py`）

全部需要 `Authorization: Bearer <TOTALCLAW_QIYE_API_KEYS>`（qiye-app 每次启动随机生成并注入）。既有 `GET /v1/mcp/presets`、`GET/POST /v1/mcp/servers`、`DELETE /v1/mcp/servers/{n}`、`POST /v1/mcp/servers/{n}/enable` 保持不变。

### 注册表

```
GET /v1/mcp/registry?q=&category=&page=1&pageSize=24&refresh=false&org=
→ { ok, items: [RegistryEntry(精简: 去 files)], total, page, pageSize, source: "remote"|"cache"|"builtin" }

GET /v1/mcp/registry/{id}
→ { ok, entry: RegistryEntry, manifest, tools: [...], readme_md, installed?: InstalledEntry }
```

### 计划（dry-run，不写任何文件）

```
POST /v1/mcp/plan
{ spec: "github", env?: {GITHUB_PERSONAL_ACCESS_TOKEN: "..."}, runtime?: "npx", org?: "acme" }
→ {
  ok: true,
  entry: {name, id, version, verified},
  runtime: {id: "npx", type: "stdio", launcher: "npx", available: true, reason?: "node 18 found"},
  runtime_candidates: [{id, type, available, reason}],
  rendered: { command, args, env: {GITHUB_PERSONAL_ACCESS_TOKEN: "${MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN}"}, enabled, timeout, tools },
  env_keys: { "GITHUB_PERSONAL_ACCESS_TOKEN": "MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN" },
  missing_env: [],                       # 非空 → 前端回到表单
  will_overwrite: false,
  security: { scan_verdict: "allow", findings: [], pin_ok: true, unverified: false },
  tools_preview: ["create_issue", "..."],
  warnings: []
}
400 → { detail: "..." }   # spec 无法解析 / 清单非法
```

### 安装 / 更新（异步作业，模式同 `skill_shop_api`）

```
POST /v1/mcp/install
{ spec, env?, runtime?, enabled?: bool, overwrite?: false, allow_unverified?: false,
  probe?: true, bearer_token?: "<平台 JWT，私有/付费条目用>" }
→ 202 { ok: true, job_id: "9f3c…", name: "github", status: "running", poll_url: "/v1/mcp/jobs/9f3c…" }
409 → 同名作业进行中
422 → { detail: "missing_env", missing_env: ["GITHUB_PERSONAL_ACCESS_TOKEN"] }

POST /v1/mcp/servers/{name}/update        → 202（同上）
DELETE /v1/mcp/servers/{name}             → 既有；扩展为同时清理 installed.json / schema-cache / mcp-tokens

GET /v1/mcp/jobs                          → { ok, jobs: [JobSummary] }
GET /v1/mcp/jobs/{job_id}?tail=200
→ { ok, job: {
     job_id, name, op: "install"|"update",
     status: "running"|"done"|"failed"|"saved_disabled",
     stage: "resolve"|"download"|"verify"|"render"|"write"|"probe"|"reload"|"finalize",
     started_at, finished_at, log: ["[resolve] github@2025.4.8 (verified)", "[download] 2 files 11.2KB", "[verify] sha256 ok · signature ok", "[write] config.yaml mcp_servers.github · .env 1 key", "[probe] connected 412ms · 26 tools", "[reload] added=[github] retained=3"],
     result?: InstalledEntry, error?: { code: "probe_failed"|"verify_failed"|"blocked"|"missing_env"|"launcher_missing", message } } }
```

### 已安装 / 状态 / 重载

```
GET /v1/mcp/installed
→ { ok, items: [InstalledEntry] }
InstalledEntry = {
  name, id?, version?, source: "registry"|"preset"|"manual", runtime?: "npx",
  installed_at?, bundle_sha256?,
  enabled: bool, state: "ready"|"connecting"|"failed"|"disabled", tools: number,
  needs_setup: bool, missing_env: string[], update_available?: {version},
  transport: "stdio"|"http"
}

GET  /v1/mcp/status        → { ok, servers: get_mcp_status() }
POST /v1/mcp/reload        → { ok, added: [], removed: [], changed: [], retained: [], tools: 41 }
```

---

## ③ agent CLI

所有子命令支持 `--json`（单个 JSON 对象到 stdout，日志到 stderr）；退出码 `0` 成功 / `1` 错误 / `2` 缺必填 env / `3` 探测失败已保存为 disabled。

```
totalclaw mcp search <q> [--category C] [--verified] [--json]
totalclaw mcp info <spec> [--json]
totalclaw mcp plan <spec> [--env K=V ...] [--runtime ID] [--json]
totalclaw mcp install <spec> [--env K=V ...] [--runtime ID] [--yes] [--no-probe]
                             [--disabled] [--allow-unverified] [--overwrite] [--json]
totalclaw mcp update [<name> | --all] [--json]
totalclaw mcp uninstall <name> [--yes] [--json]
totalclaw mcp installed [--json]
totalclaw mcp status [--json]
totalclaw mcp reload [--json]
```

`--json` 输出与 ② 的响应体一致（`install` 同步执行并直接返回 `job` 对象）。

环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `TOTALCLAW_MCP_REGISTRY` | `https://gitee.com/jlzdyx/totalclaw-mcp/raw/master/registry.json` | 注册表 URL（同 `TOTALCLAW_TOOL_REGISTRY` 风格） |
| `TOTALCLAW_MCP_API_BASE` | `https://mcp.taituai.com/api` | 平台 API（搜索 / 遥测 / 私有），不可达时降级到快照 |
| `TOTALCLAW_MCP_REGISTRY_TTL` | `3600` | 本地缓存秒数 |
| `TOTALCLAW_MCP_REQUIRE_SIGNATURE` | unset | `1` → 无签名拒绝（同 `TOTALCLAW_PLUGIN_REQUIRE_SIGNATURE`） |
| `TOTALCLAW_MCP_TELEMETRY` | `1` | `0` 关闭安装遥测 |
| `TOTALCLAW_MCP_ORG` | unset | 企业 org 标识，替换 `hosted` 运行时 URL 中的 `{org}` |
