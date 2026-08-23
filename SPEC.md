# mcp.yaml 清单规范 v1

`mcp.yaml` 是 totalclaw-mcp 注册表中每个 MCP 服务器的**单一事实源**。平台与 agent 都只认它：平台据此生成 `registry.json`、渲染市场页、探测工具；agent 据此确定性渲染 `$TOTALCLAW_HOME/config.yaml::mcp_servers.<name>`。

约定沿用 `totalclaw-plugins/SPEC.md` 与 `totalclaw-tools/SPEC.md`（`manifest_version` / `requires_protocol_version` / `tested_with` / `name` / `display_name` / `version` / `requires_env` 富对象），并新增 MCP 专属的 `runtimes` / `defaults` / `tools` / `security`。

## 1. 目录与寻址

```
registry/servers/<category>/<name>/
  mcp.yaml        # 必需
  README.md       # 推荐：安装前置、获取凭据步骤
  icon.svg|png    # 可选；有就会被投影成索引的 `icon` 字段（相对路径），
                  # 没有则客户端回落到按「首字 + 分类取色」生成的字母块。
                  # 厂商 logo 有商标，不自造假图标
  tools.json      # CI 生成：探测到的工具快照（名称/描述/inputSchema/readOnlyHint）
```

- `name`：`^[a-z0-9][a-z0-9_-]*$`，**必须与目录名一致**，发布后永不改名。它将直接成为 agent 里的 `mcp_servers.<name>` 键、toolset `mcp-<name>` 与工具前缀 `mcp__<name>__*`。
- `category`：`^[a-z0-9][a-z0-9_]*$`，等于上级目录名。推荐集合：`dev` `web` `social` `media` `biz` `data` `office` `creative` `infra` `comm` `ai`。
- `id` 由生成器派生：`totalclaw-mcp/<category>/<name>`，不要手写。
- 安装 spec 语法：`name` | `name@<version>` | `totalclaw-mcp/<category>/<name>` | `https://…/mcp.yaml` | `./本地目录`。`@version` 必须等于注册表当前版本（仓库只提供最新版；历史版本由 `api/` 的 `mcp_versions` 提供）。

## 2. 字段

### 2.1 头部（与 plugins/tools 一致）

| 字段 | 必需 | 说明 |
|---|---|---|
| `manifest_version` | ✅ | 固定 `1` |
| `requires_protocol_version` | ✅ | `">=1"`（安装器 strict 校验） |
| `tested_with` | 推荐 | agent 版本下限，PEP 440，软检查（如 `">=0.63.72"`） |
| `name` | ✅ | 见 §1 |
| `display_name` | ✅ | 展示名（中文界面用） |
| `display_name_en` | 推荐 | 英文展示名。用厂商**既有的**英文品牌名，没有就留空回落中文——留空好过现译一个错的 |
| `version` | ✅ | semver 或上游版本号；清单任何改动必须递增 |
| `description` | ✅ | 一句话能力与边界（英文） |
| `description_zh` | 推荐 | 中文描述 |
| `author` | ✅ | 上游作者 / 维护方 |
| `license` / `homepage` / `repository` | 推荐 | |
| `category` | ✅ | 见 §1 |
| `tags` | 可选 | 字符串数组 |
| `kind` | ✅ | 固定 `mcp_server` |
| `platforms` | 可选 | `[darwin, linux, win32]` 子集，缺省全平台 |
| `i18n` | 可选 | `{zh_CN: {display_name, description}}` |

### 2.2 `runtimes[]` — 候选运行时（至少 1 个）

每个元素描述一种把该服务器跑起来的方式。agent 只支持两种传输：`stdio` 与 `http`（streamable-HTTP）。**不要写 `sse` / `websocket`**——agent 的 `transport` 字段是惰性的，只会按 `url` 是否存在判断。

| 字段 | 适用 | 说明 |
|---|---|---|
| `id` | 全部 | 运行时标识，同一清单内唯一（如 `npx` `uvx` `docker` `remote` `hosted`） |
| `type` | 全部 | `stdio` \| `http` |
| `launcher` | stdio | `npx` \| `uvx` \| `pipx` \| `docker` \| `node` \| `python` \| `binary`；安装器据此检查本机可用性（`shutil.which`） |
| `command` | stdio | 可执行文件 |
| `args` | stdio | 参数列表。`npx/uvx/pipx/bunx/pnpx` 包名**必须精确 pin 版本**（`pkg@1.2.3` / `pkg==1.2.3`），docker 镜像必须带 tag，推荐带 `@sha256:` digest。`${VAR}` / `${VAR:-default}` 允许 |
| `requires` | stdio | 本机前置，如 `{node: ">=18"}`、`{python: ">=3.10"}`、`{docker: true}` |
| `url` | http | 端点 URL。`{org}` 占位符仅允许出现在 `hosted` 运行时，由安装器替换 |
| `auth` | http | `none` \| `header` \| `oauth`。`header` → 安装器生成 `headers.Authorization: Bearer ${MCP_<NAME>_API_KEY}`；`oauth` → 写 `auth: oauth`，装后需 `totalclaw mcp login <name>` |
| `headers` | http | 额外请求头（值可含 `${VAR}`）；不要把 `Authorization` 写死在这里，用 `auth: header` |
| `oauth` | http | `auth: oauth` 时可选：`{scope, client_name}`；企业 BYO 端点用 `{authorize_endpoint, token_endpoint, client_id, scopes}`（必须 https） |
| `hosted` | http | `true` 表示这是平台托管端点（M3） |

**禁止**：`command` 为 `bash/sh/zsh/cmd/powershell/pwsh` 且 `args` 含 `curl/wget/nc/socat/telnet` —— agent `mcp_security` 会拒绝连接。

### 2.3 `requires_env[]` / `optional_env[]`

```yaml
requires_env:
  - name: GITHUB_PERSONAL_ACCESS_TOKEN   # ^[A-Za-z_][A-Za-z0-9_]*$
    description: GitHub PAT (repo scope)
    prompt: 请输入 GitHub Personal Access Token
    secret: true            # true → 只进 .env，表单用密码框，日志脱敏
    required: true
    runtimes: [npx, docker] # 省略 = 所有 runtime 都需要
    default: null           # 仅 optional_env 可给默认值
    validate: "^(ghp|github_pat)_"   # 可选正则
    doc_url: https://github.com/settings/tokens   # 去哪儿申请这个凭据
    doc_label: 前往 GitHub 创建 Personal Access Token   # 链接文案，省略则用通用文案
```

`doc_url` / `doc_label` 是给界面用的：安装向导在凭据那一步把它渲染成链接。
少了它，用户看到「请输入 XXX_API_KEY」也不知道去哪儿弄——凭据填不上，
条目就等于装不了。有 `doc_url` 的条目，`prompt` 与 `description` 也应当写成
厂商自己的说法（在哪个菜单、复制哪一项），而不是「XX 所需的 XXX_API_KEY」这种同义反复。

安装器落盘规则：`.env` 键默认 `MCP_<NAME_UPPER>_<VAR>`（`NAME` 按 `[^A-Za-z0-9_]→_` 规整），config 中 `env.<VAR>: "${MCP_<NAME_UPPER>_<VAR>}"`。这样同名变量在不同服务器间不冲突，也与 `mcp_admin` 的 `MCP_<NAME>_API_KEY` 约定同构。

可选字段 `env_key`：显式指定 `.env` 键名（不做命名空间化）。用于上游约定固定变量名、或从 agent presets 导入的种子（如 `COMPOSIO_API_KEY`、`MCP_FS_ROOT`），保证既有用户 `.env` 零迁移。此时 runtime 的 `args` / `env` / `headers` 中可直接引用 `${<env_key>}`，安装器原样保留该字面量，只校验 `env_key` 已在 `requires_env` / `optional_env` 中声明。

### 2.4 `defaults` — 原样并入 `mcp_servers.<name>` 的非传输字段

只允许 agent 已支持的键：`enabled` `timeout` `connect_timeout` `keepalive_interval` `supports_parallel_tool_calls` `tools{include,exclude,resources,prompts}` `sampling{…}` `elicitation{…}` `apps{…}` `identity`。`tools.include/exclude` 使用**原始**工具名（过滤发生在加 `mcp__` 前缀之前）。

### 2.5 `tools` — 探测快照（CI 生成，人工不要手改）

```yaml
tools:
  probed_at: "2026-08-20T03:00:00Z"
  probed_runtime: npx
  count: 26
  file: tools.json          # [{name, description, read_only, input_schema}]
```

安装器把 `tools.json` 转成 agent 的 `mcp/schema-cache/<name>.json`，配合 `TOTALCLAW_MCP_LAZY_START=1` 实现"装完立刻可见工具，首次调用才真正拉起进程"。

### 2.6 `security` — 发布前扫描结论（CI 生成）

```yaml
security:
  scan_verdict: allow       # allow | warn | ask | block（与 skills_guard 同语义）
  prompt_injection_findings: []   # 工具描述里命中的注入模式
  osv: clean                # clean | advisories:<n>
  egress: [api.github.com]  # 探测期间观察到的出网域名
```

安装器门禁：`block` 永不安装；`ask` 需 `--yes/--force`；`warn` 提示；未 `verified` 的条目即使 `allow` 也需 `--allow-unverified` 且默认 `enabled: false`。

## 3. 渲染示例

输入（节选）：

```yaml
name: github
runtimes:
  - {id: npx, type: stdio, launcher: npx, command: npx,
     args: ["-y", "@modelcontextprotocol/server-github@2025.4.8"]}
requires_env:
  - {name: GITHUB_PERSONAL_ACCESS_TOKEN, secret: true, required: true}
defaults: {enabled: true, timeout: 120, tools: {exclude: [delete_repository]}}
```

输出 `config.yaml`：

```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github@2025.4.8"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN}"
    enabled: true
    timeout: 120
    tools:
      exclude: [delete_repository]
```

输出 `.env`：

```
MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx
```

agent 可见工具：`mcp__github__create_issue` …；toolset：`mcp-github`（别名 `github`）。

## 4. 校验清单（`scripts/gen_registry.py` 与 agent 安装器共同执行）

1. `manifest_version == 1`；`kind == mcp_server`；`name` / `category` 字符集；`name` 等于目录名。
2. `version` 非空；同一 `name` 全仓唯一。
3. `runtimes` 非空；每个 runtime 的 `type` ∈ {stdio, http}；stdio 必有 `command`，http 必有 `url`；不得同时给 `command` 与 `url`。
4. 包版本 pin（`package_pin_problem` 规则）；`{org}` 只允许出现在 `hosted` 运行时。
5. `requires_env[].name` 合法且不与 `MCP_<NAME>_API_KEY` 冲突。
6. `defaults` 只含白名单键。
7. 若存在 `tools.file`，文件必须存在且为 JSON 数组。
