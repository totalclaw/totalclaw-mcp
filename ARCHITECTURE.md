# totalclaw-mcp 系统架构

> TotalClaw MCP 平台：MCP 服务器的 **注册中心（Registry）+ 分发（Distribution）+ 托管网关（Hosted Gateway）**。
> 定位对齐生态里的既有三套分发系统——`totalclaw-skill-shop` 之于 skills、`totalclaw-plugins` 之于 plugins、`totalclaw-tools` 之于 tools——本平台之于 MCP。
>
> 目标：**qiye-app 通过接口、totalclaw-agent 通过命令，都能从本平台一键安装 MCP 服务器，安装完即可直接被 agent 调用。**

---

## 0. 一句话结论

| 消费者 | 入口 | 落点 | 生效方式 |
|---|---|---|---|
| totalclaw-agent（命令） | `totalclaw mcp install github` | `$TOTALCLAW_HOME/config.yaml::mcp_servers.github` + `.env` 秘密 | `reload_mcp_servers()` 选择性热重载（无需重启） |
| qiye-app（接口） | `POST /v1/mcp/install {"spec":"github"}` → 202 job → 轮询 | 同上（每账号独立 `TOTALCLAW_HOME`） | 安装任务末尾调用 `POST /v1/mcp/reload` 等价逻辑 |
| 任意 MCP 客户端（Claude Code / Cursor） | 平台托管端点 `https://mcp.taituai.com/g/{org}/{server}/mcp` | 客户端自身 mcpServers 配置 | 直接连接（Phase 3） |

平台只做一件事：**把一份经过验证的 `mcp.yaml` 清单，确定性地渲染成 agent 已经支持的 `mcp_servers` 配置块**，并补齐 agent 当前缺失的"发现 → 校验 → 安装 → 热加载 → 状态回显"闭环。

---

## 1. 现状诊断（基于对 totalclaw-agent / qiye-app / skill-shop / plugins / tools 的源码调研）

### 1.1 agent 如何消费 MCP（已具备、可直接复用）

| 能力 | 位置 | 结论 |
|---|---|---|
| 唯一配置面 | `$TOTALCLAW_HOME/config.yaml` → `mcp_servers:` 映射 | 没有 `mcp.json` 导入器；所有入口最终都写这一处 |
| 传输 | `totalclaw_core/tools/mcp_tool/server_task.py` | 只有 **stdio** 与 **streamable-HTTP**（`url` 存在即 HTTP）；`transport: sse` 字段是摆设 |
| 工具命名 | `mcp_naming.py` | `mcp__<server>__<tool>`（双下划线）；文档里的 `mcp_a_b` 已过期 |
| 工具集 | `registration.py:690` | 每个服务器生成 toolset `mcp-<server>` + 别名 `<server>` |
| 编程 API | `totalclaw_core/mcp_admin.py` | `add_server / add_preset / remove_server / set_enabled / list_servers`；校验名字 `^[A-Za-z0-9_.\-]{1,64}$`；秘密自动落 `.env`（`MCP_<NAME>_API_KEY`） |
| 热重载 | `mcp_tool/__init__.py:602 reload_mcp_servers()`；`cli.py` 每 5s 轮询 config 变更；TUI/网关 `reload.mcp` RPC；聊天 `/reload-mcp` | **可以在不重启的情况下增量加载**，只重连 added/changed |
| 安全 | `mcp_security.py`、`osv_check`、`helpers.py` 注入扫描、子进程 env 白名单 | 安装器只需在落盘前再跑一遍 |
| OAuth | `mcp_oauth.py` / `mcp_dashboard_oauth.py` | 本地回环 PKCE 流程已完整，`totalclaw mcp login <name>` |
| Schema 缓存 / 懒启动 | `schema_cache.py`、`lazy_start.py` | `$TOTALCLAW_HOME/mcp/schema-cache/<server>.json`，**可由平台预填**实现"装完即有工具" |
| REST | `totalclaw_qiye_api/server.py:6307-6384` | `GET /v1/mcp/presets`、`GET/POST /v1/mcp/servers`、`DELETE /v1/mcp/servers/{n}`、`POST /v1/mcp/servers/{n}/enable` |
| 内置目录 | `mcp_presets.py`（24 条 + 5 个 bundle）、`mcp_catalog.py`（2 条） | 硬编码 Python dict，**没有任何远程注册表对接** |

### 1.2 缺口（本平台要补的）

1. **没有远程注册表**：grep `registry.modelcontextprotocol|smithery|glama|pulsemcp` 零命中。qiye-app 的"MCP 市场"实际只是 24 条 presets。
2. **没有安装任务**：`POST /v1/mcp/servers` 是同步写配置，没有"下载 → 校验 → 探测 → 发现工具 → 热加载"的作业与进度（skills 有 `/v1/skills/shop/jobs/{id}`，组件有 `/v1/install/jobs/{id}`）。
3. **qiye_api 没有 reload 端点**：`docs/integration/MCP_SERVER_MANAGEMENT.md` 明说"只改配置，热加载是调用方的事"。
4. **没有已安装元数据**：`list_servers()` 返回裸配置，无版本 / 来源 / 工具数 / 安装时间 / 校验状态。
5. **CLI 不可脚本化**：`totalclaw mcp add` 交互式（EOF 即取消）、无 `--json`、无 `--yes`、失败也 exit 0；`config set` 不能写 list/dict。
6. **qiye-app 有两套互不相通的 MCP UI**：`McpServerPanel.vue`（真写 agent 配置）与 `PluginsView.vue` + `@totalclaw/mcp-market`（Electron 内存态，不落盘，agent 根本看不见）。
7. 顺带 bug：`totalclaw dump` 的 MCP 计数永远为 0（读了 `config.mcp.servers`）；`is_mcp_tool_parallel_safe` 仍按旧单下划线前缀判断，`supports_parallel_tool_calls` 实际失效；prompt_builder 里 playwright 工具名仍是旧格式。

### 1.3 可复用的分发模板

| 模板 | 复用点 |
|---|---|
| `totalclaw-plugins` / `totalclaw-tools`（Git 仓库 + `registry.json`） | `schema_version/registry/id_scheme/source` 头、`files[].sha256` + `bundle_sha256`、`verified` 位、Ed25519 `registry.json.sig`、agent 侧 `plugin_hub._download_raw/_download_sparse/_verify_files/_signature_gate/_scan_gate` 可**原样 import**（`tool_hub.py` 就是这么做的） |
| `totalclaw-skill-shop`（NestJS + Mongo + SSR） | 搜索/分页/分类 facet、JWT SSO（`tc_token` cookie，`.taituai.com`）、开发者上传 → 审核 → `verified`、entitlements/activation-codes 付费闭环、`node-cron` 同步 |
| `skill_shop_api.py`（agent 侧） | 202 + `job_id` + `poll_url` 作业模式、`_notify_skill_change()` 装完即生效的钩子 |
| `profile_distribution_api.py` | `plan`（dry-run）→ `install` → `update` → `info` 四段式 |
| qiye-app `plugin.yaml requires_env` 富对象 | 设置向导按 `requires_env[{name,description,prompt}]` 自动渲染表单 |

---

## 2. 总体架构

```
                    开发者 / 运营                                   企业管理员
                         │ PR / 上传 mcp.yaml                            │ 私有注册表 / org key
                         ▼                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│                               totalclaw-mcp 平台                                    │
│                                                                                    │
│  ┌──────────────────┐     ┌────────────────────────┐     ┌───────────────────────┐ │
│  │ registry/ (Git)  │────▶│ api/  NestJS + Mongo   │────▶│ gateway/ 托管 MCP 网关 │ │
│  │  servers/<cat>/  │ CI  │  /api/mcp/servers ...  │     │  /g/{org}/{srv}/mcp   │ │
│  │   <name>/mcp.yaml│ 探测│  /registry.json(.sig)  │     │  streamable-HTTP      │ │
│  │  gen_registry.py │     │  SSO · 审核 · 统计      │     │  沙箱 · 凭据 · 审计    │ │
│  └──────────────────┘     └────────────────────────┘     └───────────────────────┘ │
│            │ registry.json 快照（Gitee raw / CDN）          ┌───────────────────────┐ │
│            └───────────────────────────────────────────────│ web/  SSR 市场站       │ │
│                                                            │  mcp.taituai.com      │ │
│                                                            └───────────────────────┘ │
└───────────────┬──────────────────────────────┬───────────────────────┬─────────────┘
                │ HTTPS (registry.json / api)  │ streamable-HTTP       │
                ▼                              │                       ▼
┌─────────────────────────────────┐            │        ┌──────────────────────────┐
│ totalclaw-agent                 │            │        │ 第三方 MCP 客户端          │
│  totalclaw_core/mcp_hub.py  ◀── 新增         │        │ Claude Code / Cursor ... │
│   fetch → verify → render →     │◀───────────┘        └──────────────────────────┘
│   mcp_admin.add_server →        │
│   schema-cache 预填 → probe →   │
│   reload_mcp_servers()          │
│  CLI: totalclaw mcp install     │
│  REST: /v1/mcp/install (202)    │
└───────────────▲─────────────────┘
                │ IPC → http://127.0.0.1:<port>  Bearer(随机)   每账号一个 TOTALCLAW_HOME
┌───────────────┴─────────────────┐
│ totalclaw-qiye-app (Electron)   │
│  McpMarketView（统一市场+已安装） │
│  安装向导：runtime → env 表单 →  │
│  plan 预览 → install → job 轮询  │
└─────────────────────────────────┘
```

三条原则：

1. **单一事实源是 `mcp.yaml`**（平台侧）→ 确定性渲染为 `mcp_servers.<name>`（agent 侧）。平台不发明新的运行时，只生成 agent 已经支持的配置。
2. **两条分发通道并存**：`registry.json` 静态快照（Gitee raw / CDN，零基础设施、可离线、可签名）+ `api/` 动态服务（搜索、统计、鉴权、私有、托管）。agent 只依赖前者即可工作；后者是增强。
3. **安装永远经过 agent**：qiye-app 不直接改 `config.yaml`，而是调 qiye_api → `mcp_hub.install()`。这样校验、秘密落 `.env`、热加载、多账号隔离全部只实现一次。

---

## 3. 平台组件

### 3.1 `registry/` — 清单仓库（Git，M1 即可上线）

```
registry/
  _TEMPLATE/mcp.yaml
  servers/
    dev/github/mcp.yaml        # + README.md、icon.svg、tools.json（CI 探测快照）
    web/mcp_fetch/mcp.yaml
    social/xiaohongshu/mcp.yaml
    ...
registry.json                  # 由 scripts/gen_registry.py 生成，CI --check 守护
registry.json.sig              # Ed25519，复用 totalclaw-plugins 签名方案
```

- 目录即分类：`servers/<category>/<name>/`，`id = totalclaw-mcp/<category>/<name>`，发布后永不改名（与 plugins/tools SPEC §8 一致）。
- `scripts/gen_registry.py`：遍历清单 → 校验（名字字符集、`manifest_version`、版本 pin、transport 合法性）→ 逐文件 sha256 + `bundle_sha256` → 输出 `registry.json`。
- `scripts/probe_server.py`（CI）：在沙箱里真实启动服务器，`list_tools` 生成 `tools.json`（名称/描述/inputSchema/readOnlyHint）、跑工具描述注入扫描（复用 agent `helpers.py` 的 10 条模式）、记录出网域名 → 写回 `security:` 块。**这份快照让 agent 可以预填 `schema-cache`，安装即见工具。**
- `scripts/import_presets.py`：一次性从 agent 的 `mcp_presets.py`（24）与 `mcp_catalog.py`（2）导入种子，保持名字不变（`mcp_fetch`、`playwright` …），确保已有用户配置无缝对接。

### 3.2 `api/` — 平台服务（NestJS + Mongo，复用 skill-shop 骨架，M2）

集合：`mcp_servers`（清单 + 探测快照 + 统计）、`mcp_versions`（历史版本）、`orgs` / `org_servers`（企业私有注册表）、`org_keys`（托管网关密钥）、`installs`（安装遥测）、`users`（SSO，与 totalclaw-web 共享 `JWT_SECRET`）、`entitlements` / `activation_codes`（付费，直接复用 skill-shop 模块）。

公开接口（详见 `docs/API.md`）：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/mcp/servers?q&category&transport&launcher&verified&sort&page&pageSize` | 搜索 / 分页 |
| GET | `/api/mcp/servers/:id` | 详情（含 `tools[]`、`requires_env[]`、`runtimes[]`、`security`） |
| GET | `/api/mcp/servers/:id/recipe?target=totalclaw\|claude\|cursor\|codex` | 渲染成目标客户端的配置块 |
| GET | `/api/mcp/servers/:id/files/*` | 清单目录文件（等价 `raw_base`） |
| GET | `/api/mcp/categories` · `/api/mcp/bundles` | facet；bundle 沿用 `web/social/dev/media/biz` |
| GET | `/registry.json` · `/registry.json.sig` | 静态快照（`Cache-Control: public, max-age=300`，CDN 可缓存） |
| POST | `/api/mcp/servers/:id/events` | 安装遥测 `{event: install\|probe_ok\|probe_fail\|uninstall, agent_version, os}` |
| GET/POST | `/api/orgs/:org/mcp/servers` | 企业私有清单（JWT + org 角色） |
| POST | `/api/developer/mcp` | 开发者上传 → `reviewStatus=pending` → 管理员审核 → `verified` |
| POST | `/api/admin/reviews/:id` · `/api/admin/mcp/:id/featured` | 审核 / 精选 |

### 3.3 `gateway/` — 托管 MCP 网关（Python FastAPI + `mcp` SDK，M3）

- 端点：`https://mcp.taituai.com/g/{org}/{server}/mcp`（streamable-HTTP，agent 原生支持）。
- 鉴权：`Authorization: Bearer <org_key>`；agent 侧配置只需 `url + headers`，秘密是 `${MCP_<NAME>_API_KEY}`。
- 后端：按 `(org, server)` 在容器沙箱内启动 stdio 服务器（或反代上游 remote `url`），注入平台凭据库里该 org 的凭据；限流、审计日志、org 级工具 allowlist、会话复用。
- 价值：**企业终端零运行时依赖（不装 node/uvx/docker）**、凭据集中托管不落终端、多端共享同一实例、统一审计。
- 技术选型 Python：与 agent 同一套 `mcp` SDK 与 `server_task.py` 连接经验；spawn `npx` 子进程与语言无关。

### 3.4 `web/` — SSR 市场站（Express，复用 skill-shop `server/`，M4）

列表 / 详情 / 一键复制 `totalclaw mcp install <name>` 与各客户端 JSON；SSO 登录后可见私有条目与托管端点。

---

## 4. `mcp.yaml` 清单（单一事实源，完整规范见 `SPEC.md`）

```yaml
manifest_version: 1
requires_protocol_version: ">=1"
tested_with: ">=0.63.72"           # agent 版本软检查（PEP 440）
name: github                       # ^[a-z0-9][a-z0-9_-]*$，落地为 mcp_servers.github
display_name: GitHub
version: 2025.4.8
description: Manage issues, PRs, repos via GitHub API.
description_zh: 通过 GitHub API 管理 issue / PR / 仓库。
author: modelcontextprotocol
license: MIT
homepage: https://github.com/github/github-mcp-server
category: dev
tags: [git, issues, pull-requests]
kind: mcp_server

runtimes:                          # 候选运行时，按顺序优先；agent 按本机能力/策略选一个
  - id: npx
    type: stdio
    launcher: npx                  # npx|uvx|pipx|docker|binary|python|node
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github@2025.4.8"]   # 必须 pin 版本
    requires: { node: ">=18" }
  - id: docker
    type: stdio
    launcher: docker
    command: docker
    args: ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
           "ghcr.io/github/github-mcp-server:v0.5.0"]
  - id: remote
    type: http
    url: https://api.githubcopilot.com/mcp/
    auth: header                   # none|header|oauth
  - id: hosted                     # 平台托管（M3），{org} 由安装器替换
    type: http
    url: https://mcp.taituai.com/g/{org}/github/mcp
    auth: header

requires_env:                      # 富对象 → qiye-app 自动渲染表单；secret 只进 .env
  - name: GITHUB_PERSONAL_ACCESS_TOKEN
    description: GitHub Personal Access Token (repo scope)
    prompt: 请输入 GitHub PAT
    secret: true
    required: true
    runtimes: [npx, docker]        # 仅这些运行时需要
optional_env: []

defaults:                          # 原样并入 mcp_servers.<name>
  enabled: true
  timeout: 120
  connect_timeout: 60
  tools:
    exclude: [delete_repository]   # 原始工具名（过滤发生在加前缀之前）
    resources: true
    prompts: false
  supports_parallel_tool_calls: false

tools:                             # CI 探测快照（展示 + 预填 schema-cache）
  probed_at: "2026-08-20T03:00:00Z"
  probed_runtime: npx
  file: tools.json                 # 大体积 schema 外置

security:
  scan_verdict: allow              # allow|warn|ask|block（复用 skills_guard 语义）
  prompt_injection_findings: []
  osv: clean
  egress: [api.github.com]

platforms: [darwin, linux, win32]
```

**渲染规则（`mcp.yaml` → `mcp_servers.<name>`）**

1. 选 runtime：显式 `--runtime` > org 已配置托管 > `http` > 第一个本机可用的 `stdio`（`shutil.which(launcher)`）。
2. `type: stdio` → 复制 `command/args`；`env` = `requires_env ∪ optional_env` 中属于该 runtime 的项，值写 `${MCP_<NAME>_<VAR>}`（命名空间化，避免跨服务器冲突），真值写 `.env`。
3. `type: http` → 复制 `url`；`auth: header` → `headers.Authorization: "Bearer ${MCP_<NAME>_API_KEY}"`（与 `mcp_admin._provision_bearer` 一致）；`auth: oauth` → 写 `auth: oauth`，装完提示 `totalclaw mcp login <name>`。
4. 合并 `defaults`；`enabled` 最终值 = 用户指定 > 探测成功且必填 env 齐全 → `true`，否则 `false` 并标记 `needs_setup`。
5. 必须通过 `mcp_admin._normalize_server_spec` 与 `mcp_security.validate_mcp_server_entry`，否则拒绝落盘。

---

## 5. `registry.json` 快照

```json
{
  "schema_version": 1,
  "registry": "totalclaw-mcp",
  "id_scheme": "<registry>/<category>/<name>",
  "source": "https://gitee.com/jlzdyx/totalclaw-mcp.git",
  "api_base": "https://mcp.taituai.com/api",
  "generated_at": "2026-08-22T00:00:00Z",
  "servers": [
    {
      "name": "github", "id": "totalclaw-mcp/dev/github",
      "display_name": "GitHub", "description": "...", "version": "2025.4.8",
      "author": "modelcontextprotocol", "verified": true, "tested_with": ">=0.63.72",
      "category": "dev", "tags": ["git"],
      "transports": ["stdio", "http"], "launchers": ["npx", "docker"],
      "requires_env": [{"name": "GITHUB_PERSONAL_ACCESS_TOKEN", "secret": true, "required": true}],
      "tools_count": 26, "tools": ["create_issue", "..."],
      "security": {"scan_verdict": "allow"},
      "path": "registry/servers/dev/github",
      "raw_base": "https://gitee.com/jlzdyx/totalclaw-mcp/raw/master/registry/servers/dev/github",
      "git_sparse": {"repo": "https://gitee.com/jlzdyx/totalclaw-mcp.git", "subdir": "registry/servers/dev/github"},
      "files": [{"path": "mcp.yaml", "sha256": "...", "size": 1234}, {"path": "tools.json", "sha256": "...", "size": 9876}],
      "bundle_sha256": "..."
    }
  ]
}
```

与 `totalclaw-plugins/registry.json` 的差异只有顶层键 `servers` 和若干 MCP 专属字段；agent 侧 `plugin_hub.is_hub_entry()`（需要 `path` + `files`）直接可用。

---

## 6. agent 侧改造（totalclaw-agent）

### 6.1 新模块 `totalclaw_core/mcp_hub.py`（`tool_hub.py` 的孪生）

```python
MCP_REGISTRY_URL = os.environ.get("TOTALCLAW_MCP_REGISTRY",
    "https://gitee.com/jlzdyx/totalclaw-mcp/raw/master/registry.json")   # 与 TOTALCLAW_TOOL_REGISTRY 同款
REGISTRY_CACHE = TOTALCLAW_HOME / "mcp" / "registry-cache.json"         # TTL 1h；离线回退 mcp_presets
INSTALL_DIR    = TOTALCLAW_HOME / "mcp" / "installed" / "<name>"         # mcp.yaml + tools.json 副本
LOCK_FILE      = TOTALCLAW_HOME / "mcp" / "installed.json"              # 与 skills .hub/lock.json 同构

fetch_registry(force=False) -> dict
search(q, category=None, ...) -> list[entry]
resolve(spec) -> entry          # name | name@ver | totalclaw-mcp/<cat>/<name> | https://…/mcp.yaml | ./dir
plan(spec, *, env=None, runtime=None, org=None) -> InstallPlan
    # dry-run：选定 runtime、渲染后的 mcp_servers 块（秘密脱敏）、缺失 env、launcher 可用性、
    # 版本 pin 检查、security 结论、是否覆盖已有条目 —— 不写任何文件
install(spec, *, env=None, runtime=None, enabled=None, overwrite=False,
        allow_unverified=False, probe=True, reload=True, on_log=None) -> InstallResult
update(name) / remove(name) / list_installed() / check_updates() / reload()
```

`install()` 流水线（每一步都有 `on_log` 回调供作业日志）：

```
resolve → (verified 门禁) → 下载清单目录(plugin_hub._download_raw / _download_sparse)
→ _verify_files(文件集相等 + sha256) → _signature_gate(registry.json.sig)
→ validate_manifest(SPEC) → package_pin_problem() → osv_check(command,args)
→ render(mcp.yaml → mcp_servers 块) → mcp_security.validate_mcp_server_entry
→ 写 .env 秘密(save_env_value) → mcp_admin.add_server(name, block, enabled=…)
→ 预填 mcp/schema-cache/<name>.json（来自 tools.json）
→ probe（复用 _mcp_config_impl._probe_single_server；失败则 set_enabled(False) + needs_setup）
→ reload_mcp_servers()（进程内有 MCP loop 时；否则交给 cli.py 5s 配置监视）
→ 写 installed.json + audit.log → 遥测 POST /api/mcp/servers/:id/events（可关）
```

### 6.2 CLI（`totalclaw_cli/_mcp_hub_impl.py`，挂到既有 `mcp` 子命令树）

```
totalclaw mcp search <q> [--category C] [--json]
totalclaw mcp info <spec> [--json]
totalclaw mcp plan <spec> [--env K=V ...] [--runtime ID] [--json]
totalclaw mcp install <spec> [--env K=V ...] [--runtime ID] [--yes] [--no-probe]
                             [--disabled] [--allow-unverified] [--overwrite] [--json]
totalclaw mcp update [<name> | --all] [--json]
totalclaw mcp uninstall <name> [--yes] [--json]
totalclaw mcp installed [--json]         # lock + get_mcp_status() 合并
totalclaw mcp status [--json]            # 运行态 ready/connecting/failed/disabled
totalclaw mcp reload [--json]
```

- 退出码：`0` 成功；`1` 错误；`2` 缺必填 env（`--json` 输出 `missing_env[]`，供 qiye-app 二次弹表单）；`3` 探测失败但已保存为 disabled。
- 既有 `mcp add / remove / list / test / presets / catalog` 保留；`catalog` 变为 `search` 的别名；`presets` 数据由注册表种子接管，保留为离线回退。
- 顺手修复：所有 `mcp` 子命令失败返回非零、`dump` 计数、`is_mcp_tool_parallel_safe` 前缀、文档命名。

### 6.3 qiye_api（`totalclaw_qiye_api/mcp_hub_api.py`，按 `skill_shop_api.py` 模式注册）

| 方法 | 路径 | 请求 / 响应 |
|---|---|---|
| GET | `/v1/mcp/registry?q&category&page&pageSize&refresh` | 代理 + 缓存 → `{items,total,page,pageSize}` |
| GET | `/v1/mcp/registry/{id}` | 详情（含 `tools[]`、`requires_env[]`、`runtimes[]`） |
| POST | `/v1/mcp/plan` | `{spec, env?, runtime?}` → `InstallPlan` |
| POST | `/v1/mcp/install` | `{spec, env?, runtime?, enabled?, overwrite?, allow_unverified?, bearer_token?}` → **202** `{ok, job_id, poll_url}` |
| GET | `/v1/mcp/jobs` · `/v1/mcp/jobs/{job_id}?tail=200` | `{job:{status, stage, log[], result, error}}` |
| GET | `/v1/mcp/installed` | lock + `get_mcp_status()` 合并：`[{name,id,version,runtime,enabled,state,tools,needs_setup,update_available}]` |
| POST | `/v1/mcp/servers/{name}/update` | 202 job |
| POST | `/v1/mcp/reload` | `reload_mcp_servers()` → `{added,removed,changed,retained,tools}` |
| GET | `/v1/mcp/status` | `get_mcp_status()` |

安装任务末尾调用 `_notify_mcp_change()`：`reload_mcp_servers()` + 对热池里的 agent 调 `refresh_tools()`（对应 `skill_shop_api._notify_skill_change()`）。既有 5 个 `/v1/mcp/*` 接口保持兼容。

---

## 7. qiye-app 侧改造（totalclaw-qiye-app）

1. **合并两套 UI** → `views/McpMarketView.vue`：Tab「市场」（调 `/v1/mcp/registry`）+「已安装」（`/v1/mcp/installed`，状态卡 ready / connecting / failed / needs_setup / update_available）。`PluginsView.vue` 的 MCP 段与 `@totalclaw/mcp-market` 内存注册表删除（或仅保留类型）。
2. **安装向导**（`components/mcp/McpInstallDialog.vue`）：选 runtime → 按 `requires_env` 渲染表单（沿用 plugin `requires_env` 渲染器，`secret: true` 用密码框）→ `POST /v1/mcp/plan` 预览配置块 / 工具列表 / 安全结论 → `POST /v1/mcp/install` → 轮询 job 显示阶段日志 → 完成后展示 `mcp__<name>__*` 工具数；`exit 2`（缺 env）时回到表单。
3. **IPC**：`packages/ipc-contracts` 新增 `QIYE_API_MCP_REGISTRY / REGISTRY_INFO / PLAN / INSTALL / JOB / INSTALLED / UPDATE / RELOAD / STATUS`，`qiyeApi.ipc.ts` 一律 `postRaw/getRaw`（避免 camel→snake 把 `GITHUB_TOKEN` 改坏）。
4. **版本门控**：feature id `mcp-market` 不变；按版本矩阵「专业 5 个 / 旗舰不限」在 IPC 层加 count 校验。
5. **多租户**：天然继承「一个账号 = 一个 `TOTALCLAW_HOME` = 一个 qiye-api 子进程」，无需新增 tenant 字段。企业私有注册表通过 `/v1/mcp/registry?org=` 透传 org JWT。

---

## 8. 端到端时序（qiye-app 一键安装）

```
用户            qiye-app(渲染)      main/IPC        qiye_api            mcp_hub              平台
 │ 点「安装 github」  │                 │               │                   │                   │
 │──────────────────▶│ requires_env 表单│               │                   │                   │
 │ 填 PAT ──────────▶│ POST plan ──────▶│ ─────────────▶│ plan() ──────────▶│ registry-cache    │
 │ 看预览(工具26/allow)│◀───────────────│◀──────────────│◀──────────────────│                   │
 │ 确认 ────────────▶│ POST install ───▶│ ─────────────▶│ 202 job ─────────▶│ 下载 mcp.yaml ───▶│
 │                   │ 轮询 job ───────▶│               │                   │ sha256/sig 校验    │
 │                   │  [download]      │               │                   │ render → .env      │
 │                   │  [verify]        │               │                   │ mcp_admin.add      │
 │                   │  [probe 412ms 26 tools]          │                   │ schema-cache 预填  │
 │                   │  [reload ok]     │               │                   │ probe → reload     │
 │ 状态卡 ready ◀────│◀── job done ─────│◀──────────────│◀──────────────────│ 遥测 events ──────▶│
 │ 下一轮对话即可用 mcp__github__create_issue                                                  │
```

agent CLI 路径相同，只是入口换成 `totalclaw mcp install github --env GITHUB_PERSONAL_ACCESS_TOKEN=... --yes --json`。

---

## 9. 安全模型

| 层 | 措施 | 来源 |
|---|---|---|
| 注册表可信 | `files[].sha256` + `bundle_sha256` + Ed25519 `registry.json.sig`；`verified` 仅维护者可置；未 verified 需 `--allow-unverified` 且默认 `enabled:false` | plugins SPEC §8 / `plugin_hub._signature_gate` |
| 包来源 | `npx/uvx/pipx/docker` 强制精确版本 pin（`mcp_catalog.package_pin_problem`）；docker 推荐 digest；安装时 `osv_check` | agent 既有 |
| 发布前探测 | 平台 CI 沙箱启动、工具描述注入扫描（10 模式）、出网域名记录、`scan_verdict` | `helpers.py` 模式复用 |
| 落盘前 | `mcp_security.validate_mcp_server_entry`（shell + curl/nc 出网拒绝）、`_normalize_server_spec` | agent 既有 |
| 秘密 | 只进 `.env`，键 `MCP_<NAME>_<VAR>`；config 里永远是 `${…}`；日志脱敏 `redact_stdio_argv` | `mcp_admin` 约定 |
| 运行时 | 子进程 env 白名单、断路器、审批层按 `readOnlyHint` 区分 `read_only/read_write`；清单 `defaults.tools.exclude` 预排除危险工具 | agent 既有 |
| 托管网关 | org key、限流、审计、org 级 allowlist、凭据不出平台 | M3 |

---

## 10. 分期路线

| 里程碑 | 内容 | 依赖 |
|---|---|---|
| **M1 注册表 + 安装闭环**（约 2 周） | `registry/` 仓库 + `gen_registry.py` + 27 条种子（本仓已生成：24 presets + 2 catalog，去重后 27）；agent `mcp_hub.py` + `totalclaw mcp install/search/plan/installed/reload`（`--json`）；qiye_api `/v1/mcp/registry|plan|install|jobs|installed|reload`；Gitee raw 分发 | 无需任何新服务即可跑通 |
| **M2 平台服务 + 统一 UI** | NestJS `api/` + Mongo（搜索、统计、开发者上传、审核、`registry.json` 快照 + 签名）；CI `probe_server.py` 自动生成 `tools.json`；qiye-app `McpMarketView` + 安装向导 | M1 |
| **M3 托管网关 + 企业** | `gateway/` streamable-HTTP 托管；org 私有注册表；凭据托管；付费/授权（复用 skill-shop entitlements / activation-codes） | M2 |
| **M4 市场站 + 多客户端** | SSR `web/`；`recipe?target=claude|cursor|codex`；更新通知（`check_updates` + 桌面提醒） | M2 |

---

## 11. 本仓目录

```
totalclaw-mcp/
├── ARCHITECTURE.md          # 本文
├── SPEC.md                  # mcp.yaml 规范
├── README.md
├── registry.json            # 生成物（scripts/gen_registry.py）
├── registry/
│   ├── _TEMPLATE/mcp.yaml
│   └── servers/<category>/<name>/mcp.yaml
├── scripts/
│   ├── gen_registry.py      # 索引生成 / --check
│   ├── import_presets.py    # 从 agent presets/catalog 导入种子
│   └── probe_server.py      # CI：探测 tools.json + 安全扫描（M2）
├── docs/
│   ├── API.md               # 平台 API + qiye_api 合约 + CLI 合约
│   ├── AGENT_INTEGRATION.md # agent 侧改造清单
│   └── QIYE_APP_INTEGRATION.md
├── api/README.md            # NestJS 服务（M2）
├── gateway/README.md        # 托管网关（M3）
└── web/README.md            # SSR 市场站（M4）
```
