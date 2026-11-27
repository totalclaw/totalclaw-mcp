# 上游版本追踪（2026-11-26）

> F 组（见 [`TODO.md`](TODO.md)）的明细与结果。数据由 `scripts/check_upstream_updates.py` 生成：只读 npm / PyPI 元数据，不安装、不运行任何包。
> 静态审核结果：[`review-2026-11-26-upstream.md`](review-2026-11-26-upstream.md)；人工复核：[`review-2026-11-26-upstream-manual.json`](review-2026-11-26-upstream-manual.json)。

## 结果

- 查了 473 条 npx / uvx 条目（`block`、git 来源、自研二进制、http 远程不在内），**122 条落后上游**。
- **已处理 106 条**：官方参考服务器 3 条 + stripe 迁移 1 条 + 普通升级 101 条（102 个包；mastergo 一个条目两个包）。
- **暂缓 4 条**：`@modelcontextprotocol/*` 的 npm 2.x 要求 Node ≥24，桌面端内置 Node 22.22.3。
- **下一轮 12 条**：比现钉新的版本全都发布不满 7 天。
- 静态审核 104/104 allow（77 直接通过；27 有命中，其中 20 条与已上架旧版逐项相同，7 条共 13 处新增命中逐条读过代码，均无害）。
- 门禁：`gen_registry --check --strict` 通过（650 条、0 警告），`scan-registry` 0 命中，`dep_gate --refresh` 0 处命中（npm 4472 + PyPI 890 个包版本的完整依赖树，黑名单 35 个包名），`dep_gate --check` 0 处命中。

## 怎么升的（下一轮照做）

1. `check_upstream_updates.py` 找落后条目；目标版本取**发布满 7 天的最新稳定版**（跳过预发布、弃用、撤回），不追最新——投毒版本通常几天内被发现撤回。
2. 内存里比对旧版与目标版（不安装）：启动的 bin / 入口点还在、Node / Python 下限、代码读取的环境变量增减；清单声明的变量新版不再读取就不升。带 `security.enforced_env` 的条目，确认新版仍认这个开关（这次 desktop_commander / jshook / for_blender 三条都确认过）。
3. 改 pin、清单 `version` 递增，跑 `review_static.py --name … --date <日期>-upstream`（**用单独的 date 标签**，否则会覆盖当天新增条目的审核报告）。
4. 有命中的：用同一扫描器扫旧 pin 做差分，只读新增命中；结论写进 `-manual.json` 后 `--report` 重算。
5. 升级条目慎用 `review_static.py --apply`：遇到 warn 它会把已上架条目置为未审核（等于下架），所以先复核到 allow 再写回。（它以前还会整段重写 `security:`、丢掉 `enforced_env`，已在 U4.2 修掉。）
6. 带 `tools.json` 的条目重新探测（`probe_server.py`，需要凭据的会跳过），再 `gen_registry.py`、`--check --strict`、`--scan-registry`、`dep_gate.py --refresh`。

## F 组任务

### U1 · 官方参考服务器

| 状态 | 条目 | 方式 | 包 | 旧 | 新 | 说明 |
|---|---|---|---|---|---|---|
| [x] | mcp_fetch | uvx | `mcp-server-fetch` | 2026.8.18 | 2026.11.18 | 新版改依赖 MCP SDK v2（`mcp>=2.3`），去掉了清单里的 `--with mcp<2`（否则装不上）；Python 下限升到 3.11.5。实测探测通过 |
| [x] | mcp_git | uvx | `mcp-server-git` | 2026.8.18 | 2026.11.18 | 实测探测通过（12 → 14 个工具） |
| [x] | mcp_time | uvx | `mcp-server-time` | 2026.8.18 | 2026.11.18 | 实测探测通过（2 → 3 个工具） |
| [ ] | mcp_filesystem | npx | `@modelcontextprotocol/server-filesystem` | 2026.7.10（已弃用） | 2.4.0 | 暂缓：要求 Node ≥24 |
| [ ] | mcp_memory | npx | `@modelcontextprotocol/server-memory` | 2026.7.4（已弃用） | 2.2.1 | 暂缓：要求 Node ≥24 |
| [ ] | mcp_sequential_thinking | npx | `@modelcontextprotocol/server-sequential-thinking` | 2026.7.4（已弃用） | 2.2.0 | 暂缓：要求 Node ≥24 |
| [ ] | mcp_everything | npx | `@modelcontextprotocol/server-everything` | 2026.8.18（已弃用） | 2.3.1 | 暂缓：要求 Node ≥24 |

SDK v2 的服务端收到旧式 `initialize` 会回落到旧协议，agent 的 MCP 客户端（SDK 1.27.2，最高协议 2025-11-25）实测能连上。
日期版虽已弃用，npm 上仍可安装，暂缓的 4 条继续可用。

- [x] **U1.8** agent `totalclaw_core/tools/mcp_presets.py` 的 `mcp-server-time` 同步到 2026.11.18（工作区已改、未提交；sequential-thinking 随 Node 24 暂缓）。
- [ ] **U1.9** 桌面端内置 Node 升到 24 后，再升上面 4 条 npm 包（跨仓：qiye-app 的 `NODE_VERSION`）。

### U2 · 上游停止维护

- [x] **U2.1** `stripe`：`@stripe/mcp` 已停止维护、不再有安全修复。改成官方托管端点 `https://mcp.stripe.com`（`auth: oauth`），去掉 `STRIPE_SECRET_KEY`。已实测：端点返回 401 + RFC 9728 资源元数据，授权服务器 `access.stripe.com/mcp` 支持动态注册 + PKCE。

### U3 · 老用户升级路径（F8 结论）

- 桌面端「已安装」页有「更新」按钮（`POST /v1/mcp/servers/{name}/update`，按注册表重装），老用户点了就能换到新 pin；stripe 老用户点更新会从 npx 换到托管端点。
- [ ] **U3.1** 没有「有新版本」提示：已安装页不比对注册表版本，用户不知道该点。建议桌面端按 `installed.json` 的 version 与注册表 version 比较，显示提示。
- [ ] **U3.2** 内置 preset 装的（source ≠ registry）「更新」按钮置灰，拿不到注册表里的新版本。

### U4 · 顺带发现（不是这次升级引入的）

- [x] **U4.1**（已修，TODO F9）desktop_commander 的 `postinstall`（`dist/track-installation.js`）会向 `telemetry.desktopcommander.app` 上报一次安装事件，**不检查** `DESKTOP_COMMANDER_DISABLE_TELEMETRY`。我们强制的关遥测只管运行期，管不到安装期。可选修法：给该条目加 `npm_config_ignore_scripts=true`（postinstall 里另一步 verify-ripgrep 失败本来就会被忽略），需实测后再定。
- [x] **U4.2** `review_static.py --apply` 以前会丢 `security.enforced_env`（见上文第 5 步）。已修：只换 `scan_verdict` / `osv` / `reason`，其余键原样保留，写回前断言没被改动。

### 已升级（102 个包 / 101 个条目）

目标版本 = 发布满 7 天的最新稳定版，所以不一定等于上游最新。「复核」列：直接通过 = 扫描零命中；差分 = 有命中但与已上架旧版相同；已读 = 有新增命中、逐条读过代码判定无害（理由见 `review-2026-11-26-upstream-manual.json`）。

| 状态 | 条目 | 方式 | 包 | 旧 | 新 | 跨度 | 上游最新 | 复核 |
|---|---|---|---|---|---|---|---|---|
| [x] | basic_memory | uvx | `basic-memory` | 0.24.1 | 1.0.0 | major | 1.0.0 | 已读 |
| [x] | davinci_resolve | npx | `davinci-resolve-mcp` | 4.15.5 | 5.3.4 | major | 5.5.3 | 差分 |
| [x] | dsh_novel_writer | npx | `dsh-novel-writer` | 6.9.0 | 7.4.0 | major | 8.3.0 | 直接通过 |
| [x] | socialcrawl | npx | `socialcrawl-mcp` | 1.9.0 | 2.2.0 | major | 2.3.0 | 已读 |
| [x] | speakai | npx | `@speakai/mcp-server` | 1.39.0 | 2.1.1 | major | 2.4.0 | 直接通过 |
| [x] | actors | npx | `@apify/actors-mcp-server` | 0.19.5 | 0.21.12 | minor(0.x) | 0.23.0 | 直接通过 |
| [x] | atlassian | uvx | `mcp-atlassian` | 0.23.1 | 0.24.6 | minor(0.x) | 0.24.8 | 差分 |
| [x] | canli_validation | npx | `canli-validation-mcp` | 0.14.1 | 0.16.0 | minor(0.x) | 0.16.0 | 直接通过 |
| [x] | clawtouch | uvx | `clawtouch-mcp` | 0.5.2 | 0.6.1 | minor(0.x) | 0.6.1 | 直接通过 |
| [x] | code_graph_rag | uvx | `code-graph-rag` | 0.3.13 | 0.7.1 | minor(0.x) | 0.7.129 | 已读 |
| [x] | concord | npx | `@concord-ai/concord-mcp` | 0.17.1 | 0.23.0 | minor(0.x) | 0.25.0 | 差分 |
| [x] | datetime | uvx | `mcp-datetime` | 0.1.4 | 0.3.0 | minor(0.x) | 0.3.0 | 直接通过 |
| [x] | fetcher | npx | `fetcher-mcp` | 0.3.9 | 0.4.1 | minor(0.x) | 0.4.1 | 差分 |
| [x] | local | npx | `@awareness.market/local` | 0.21.1 | 0.22.1 | minor(0.x) | 0.22.1 | 差分 |
| [x] | lrvx | uvx | `lrvx-mcp` | 0.11.0 | 0.12.1 | minor(0.x) | 0.12.1 | 直接通过 |
| [x] | marketplaces_ru | uvx | `marketplaces-mcp-ru` | 0.6.1 | 0.7.0 | minor(0.x) | 0.7.0 | 直接通过 |
| [x] | memory | npx | `@mnemoverse/mcp-memory-server` | 0.16.0 | 0.18.1 | minor(0.x) | 0.18.1 | 差分 |
| [x] | ms_365 | npx | `@softeria/ms-365-mcp-server` | 0.175.0 | 0.187.0 | minor(0.x) | 0.191.1 | 直接通过 |
| [x] | search1api | npx | `search1api-mcp` | 0.9.0 | 0.12.0 | minor(0.x) | 0.15.0 | 直接通过 |
| [x] | sentry | npx | `@sentry/mcp-server` | 0.37.0 | 0.50.0 | minor(0.x) | 0.51.0 | 直接通过 |
| [x] | supabase_2 | npx | `@supabase/mcp-server-supabase` | 0.14.0 | 0.18.0 | minor(0.x) | 0.21.0 | 直接通过 |
| [x] | taskade | npx | `@taskade/mcp-server` | 0.1.4 | 0.2.1 | minor(0.x) | 0.2.1 | 直接通过 |
| [x] | transcriptfetch | npx | `transcriptfetch-mcp` | 0.2.8 | 0.3.1 | minor(0.x) | 0.3.1 | 直接通过 |
| [x] | zotero | uvx | `zotero-mcp-server` | 0.15.1 | 0.17.2 | minor(0.x) | 0.17.4 | 差分 |
| [x] | aiven | npx | `mcp-aiven` | 1.18.0 | 1.20.0 | minor | 1.21.0 | 直接通过 |
| [x] | bernstein | uvx | `bernstein` | 3.23.0 | 3.24.1 | minor | 4.0.2 | 差分 |
| [x] | brightdata | npx | `@brightdata/mcp` | 4.1.0 | 4.8.0 | minor | 4.10.0 | 直接通过 |
| [x] | browsermcp | npx | `@browsermcp/mcp` | 2.1.0 | 2.5.0 | minor | 2.5.0 | 直接通过 |
| [x] | chrome_devtools | npx | `chrome-devtools-mcp` | 1.7.0 | 1.13.0 | minor | 1.14.0 | 直接通过 |
| [x] | context7 | npx | `@upstash/context7-mcp` | 4.4.4 | 4.7.3 | minor | 4.9.0 | 直接通过 |
| [x] | excel_haris_musa | uvx | `excel-mcp-server` | 2.2.2 | 2.3.2 | minor | 2.3.7 | 直接通过 |
| [x] | firecrawl | npx | `firecrawl-mcp` | 3.36.0 | 3.40.0 | minor | 3.41.0 | 直接通过 |
| [x] | for_blender | uvx | `mcp-for-blender` | 2.2.4 | 2.3.1 | minor | 2.3.3 | 已读 |
| [x] | frontrun | npx | `frontrun-mcp-server` | 2.7.0 | 2.8.3 | minor | 2.8.3 | 直接通过 |
| [x] | kagimcp | uvx | `kagimcp` | 1.0.2 | 1.1.0 | minor | 1.2.0 | 直接通过 |
| [x] | keboola | uvx | `keboola-mcp-server` | 1.110.0 | 1.120.0 | minor | 1.120.1 | 差分 |
| [x] | kordoc | npx | `kordoc` | 4.24.14 | 4.25.1 | minor | 4.25.24 | 直接通过 |
| [x] | leetcode | npx | `@jinzcdev/leetcode-mcp-server` | 1.4.0 | 1.5.1 | minor | 1.5.1 | 直接通过 |
| [x] | mongo | npx | `mcp-mongo-server` | 3.0.1 | 3.2.1 | minor | 3.2.1 | 直接通过 |
| [x] | mongodb | npx | `mongodb-mcp-server` | 3.1.0 | 3.3.0 | minor | 3.4.0 | 直接通过 |
| [x] | n8n | npx | `n8n-mcp` | 2.99.2 | 2.103.1 | minor | 2.104.0 | 直接通过 |
| [x] | notion_notionhq | npx | `@notionhq/notion-mcp-server` | 2.5.2 | 2.6.1 | minor | 2.6.1 | 直接通过 |
| [x] | openosint | uvx | `openosint` | 2.36.1 | 2.38.2 | minor | 2.38.2 | 差分 |
| [x] | piia_engram | uvx | `piia-engram` | 4.26.0 | 4.27.0 | minor | 4.29.0 | 差分 |
| [x] | safari | npx | `safari-mcp` | 2.22.19 | 2.24.1 | minor | 2.24.2 | 差分 |
| [x] | screenshotone | npx | `@screenshotone/mcp` | 1.1.1 | 1.3.0 | minor | 1.3.0 | 直接通过 |
| [x] | searxng | npx | `mcp-searxng` | 2.9.0 | 2.11.0 | minor | 2.12.0 | 直接通过 |
| [x] | toolbox_sdk | npx | `@toolbox-sdk/server` | 1.15.0 | 1.17.0 | minor | 1.18.0 | 直接通过 |
| [x] | agent_recall | npx | `agent-recall-mcp` | 3.5.2 | 3.5.3 | patch | 3.5.4 | 直接通过 |
| [x] | anymd | npx | `@sylphx/anymd` | 8.5.5 | 8.5.13 | patch | 8.5.17 | 直接通过 |
| [x] | azure_devops | npx | `@tiberriver256/mcp-server-azure-devops` | 0.1.53 | 0.1.54 | patch | 0.2.0 | 直接通过 |
| [x] | bestax | npx | `bestax-mcp` | 1.18.13 | 1.18.79 | patch | 1.18.98 | 直接通过 |
| [x] | bhived | npx | `bhived-mcp` | 1.4.0 | 1.4.2 | patch | 1.4.2 | 直接通过 |
| [x] | bigquery_lucashild | uvx | `mcp-server-bigquery` | 0.3.2 | 0.3.3 | patch | 0.3.3 | 直接通过 |
| [x] | bilibili | npx | `@xzxzzx/bilibili-mcp` | 1.14.5 | 1.14.6 | patch | 1.14.6 | 直接通过 |
| [x] | brave_search | npx | `@brave/brave-search-mcp-server` | 2.1.4 | 2.1.5 | patch | 2.2.0 | 直接通过 |
| [x] | contextstream | npx | `@contextstream/mcp-server` | 1.0.36 | 1.0.83 | patch | 1.0.109 | 直接通过 |
| [x] | dchub | npx | `dchub-mcp-server` | 2.12.44 | 2.12.59 | patch | 2.12.64 | 直接通过 |
| [x] | dcs_cloud | npx | `dcs-cloud-mcp-server` | 2.0.0 | 2.0.3 | patch | 2.0.3 | 差分 |
| [x] | desktop_commander | npx | `@wonderwhy-er/desktop-commander` | 0.3.1 | 0.3.4 | patch | 0.3.4 | 差分 |
| [x] | dexpaprika | npx | `dexpaprika-mcp` | 2.9.2 | 2.9.5 | patch | 2.9.6 | 直接通过 |
| [x] | dnstwist | npx | `@burtthecoder/mcp-dnstwist` | 1.1.1 | 1.1.4 | patch | 1.1.4 | 直接通过 |
| [x] | egc | npx | `@egchq/egc` | 1.1.23 | 1.1.25 | patch | 1.1.25 | 已读 |
| [x] | elasticsearch | uvx | `elasticsearch-mcp-server` | 2.1.6 | 2.1.9 | patch | 2.1.9 | 直接通过 |
| [x] | evc_team_relay | uvx | `evc-team-relay-mcp` | 1.0.9 | 1.0.10 | patch | 1.0.10 | 直接通过 |
| [x] | exa_2 | npx | `exa-mcp-server` | 3.4.2 | 3.4.3 | patch | 3.5.1 | 直接通过 |
| [x] | find | npx | `@agentage/find-mcp` | 1.13.2 | 1.13.5 | patch | 1.13.6 | 直接通过 |
| [x] | genieacs | npx | `genieacs-mcp` | 0.4.0 | 0.4.2 | patch | 0.4.2 | 差分 |
| [x] | github_atomicmail | npx | `@atomicmail/mcp-github` | 0.3.31 | 0.3.34 | patch | 0.3.34 | 直接通过 |
| [x] | gitlab | npx | `@zereight/mcp-gitlab` | 2.3.13 | 2.3.29 | patch | 3.1.0 | 直接通过 |
| [x] | google_news | npx | `@chanmeng666/google-news-server` | 1.0.1 | 1.0.2 | patch | 1.0.2 | 直接通过 |
| [x] | infimind_video | npx | `@infimind/video-mcp-cli` | 1.0.11 | 1.0.15 | patch | 1.0.15 | 差分 |
| [x] | ipinfo | uvx | `mcp-server-ipinfo` | 0.7.0 | 0.7.1 | patch | 0.7.1 | 直接通过 |
| [x] | jshook | npx | `@jshookmcp/jshook` | 0.4.2 | 0.4.7 | patch | 0.4.7 | 直接通过 |
| [x] | kubernetes | npx | `mcp-server-kubernetes` | 4.2.1 | 4.2.3 | patch | 4.2.3 | 直接通过 |
| [x] | linear_tacticlaunch | npx | `@tacticlaunch/mcp-linear` | 1.4.5 | 1.4.6 | patch | 1.4.6 | 差分 |
| [x] | livetennisapi | npx | `livetennisapi-mcp` | 1.6.4 | 1.6.5 | patch | 1.6.5 | 直接通过 |
| [x] | lockdocs | npx | `@sylphx/lockdocs` | 0.7.0 | 0.7.5 | patch | 0.7.12 | 直接通过 |
| [x] | maigret | npx | `mcp-maigret` | 1.0.17 | 1.0.22 | patch | 1.0.22 | 直接通过 |
| [x] | mastergo | npx | `@mastergo/magic-mcp` | 0.2.8 | 0.2.20 | patch | 0.2.23 | 已读 |
| [x] | mastergo | npx | `@mastergo/vibe-mcp` | 1.0.28 | 1.0.32 | patch | 1.0.33 | 差分 |
| [x] | mcptoon | uvx | `mcptoon` | 0.8.31 | 0.8.40 | patch | 0.8.41 | 差分 |
| [x] | minimax | uvx | `minimax-mcp` | 0.0.19 | 0.0.20 | patch | 0.0.20 | 直接通过 |
| [x] | mobile | npx | `@mobilenext/mobile-mcp` | 1.0.14 | 1.0.18 | patch | 1.0.20 | 直接通过 |
| [x] | mongodb_lens | npx | `mongodb-lens` | 9.1.4 | 9.1.5 | patch | 9.2.0 | 直接通过 |
| [x] | motherduck | uvx | `mcp-server-motherduck` | 1.1.0 | 1.1.1 | patch | 1.1.1 | 直接通过 |
| [x] | mysql | uvx | `mysql-mcp-server` | 0.4.4 | 0.4.5 | patch | 0.4.5 | 直接通过 |
| [x] | naver_search | npx | `@isnow890/naver-search-mcp` | 1.0.54 | 1.0.55 | patch | 1.1.1 | 直接通过 |
| [x] | openhire | uvx | `openhire` | 0.8.28 | 0.8.73 | patch | 0.8.79 | 已读 |
| [x] | opik | uvx | `opik-mcp` | 3.0.7 | 3.0.11 | patch | 3.0.13 | 直接通过 |
| [x] | oxylabs | uvx | `oxylabs-mcp` | 0.10.0 | 0.10.2 | patch | 0.10.2 | 直接通过 |
| [x] | playwright | npx | `@playwright/mcp` | 0.0.79 | 0.0.86 | patch | 0.0.86 | 直接通过 |
| [x] | rad_security | npx | `@rad-security/mcp-server` | 0.0.47 | 0.0.49 | patch | 0.0.50 | 直接通过 |
| [x] | screenpipe | npx | `screenpipe-mcp` | 0.20.3 | 0.20.4 | patch | 0.22.0 | 差分 |
| [x] | semble | uvx | `semble` | 0.7.0 | 0.7.3 | patch | 0.7.4 | 直接通过 |
| [x] | shell | uvx | `mcp-shell-server` | 1.1.14 | 1.1.15 | patch | 1.1.15 | 直接通过 |
| [x] | shodan | npx | `@burtthecoder/mcp-shodan` | 1.0.34 | 1.0.41 | patch | 1.0.41 | 直接通过 |
| [x] | threatcluster | npx | `threatcluster-mcp` | 0.2.5 | 0.2.7 | patch | 0.2.8 | 直接通过 |
| [x] | virustotal | npx | `@burtthecoder/mcp-virustotal` | 1.0.35 | 1.0.40 | patch | 1.0.40 | 直接通过 |
| [x] | webclaw | npx | `@webclaw/mcp` | 0.7.0 | 0.7.4 | patch | 0.7.5 | 直接通过 |
| [x] | weisheng_scrm | npx | `mcp-server-weisheng-scrm` | 0.0.6 | 0.0.7 | patch | 0.0.7 | 差分 |
| [x] | yfmcp | uvx | `yfmcp` | 0.14.0 | 0.14.1 | patch | 0.14.1 | 直接通过 |

### 冷却期内、下一轮再升（12 条）

这些包落后上游，但比当前 pin 新的版本全部发布不满 7 天。

| 状态 | 条目 | 方式 | 包 | 现钉 | 上游最新 | 发布日期 |
|---|---|---|---|---|---|---|
| [ ] | airtable_rashidazarang | npx | `@rashidazarang/airtable-mcp` | 4.0.1 | 5.1.0 | 2026-11-19 |
| [ ] | arxiv_latex | uvx | `arxiv-latex-mcp` | 0.3.0 | 0.4.0 | 2026-11-22 |
| [ ] | cos | npx | `cos-mcp` | 1.0.15 | 1.1.1 | 2026-11-25 |
| [ ] | data_studio | npx | `@geek-fun/data-studio-mcp` | 0.1.12 | 0.1.13 | 2026-11-23 |
| [ ] | fetch | npx | `mcp-fetch-server` | 1.1.2 | 1.2.0 | 2026-11-25 |
| [ ] | ffmpeg_skill | npx | `ffmpeg-skill` | 4.8.3 | 4.16.0 | 2026-11-27 |
| [ ] | figwright | npx | `@figwright/mcp` | 0.7.0 | 0.8.1 | 2026-11-24 |
| [ ] | forge | npx | `@reliantlabs/forge` | 1.11.0 | 1.12.0 | 2026-11-26 |
| [ ] | mailkite | npx | `@mailkite/mcp` | 0.20.0 | 0.20.2 | 2026-11-19 |
| [ ] | perplexity_ai | npx | `@perplexity-ai/mcp-server` | 1.3.0 | 1.5.0 | 2026-11-25 |
| [ ] | phonedriver | npx | `phonedriver` | 0.1.7 | 0.1.8 | 2026-11-26 |
| [ ] | yuque | npx | `yuque-mcp` | 1.0.0 | 1.1.0 | 2026-11-20 |
