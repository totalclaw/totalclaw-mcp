# 对接任务清单（TODO）

> **给未来对接会话的入口文档。** 对接 totalclaw-agent 或 totalclaw-qiye-app 时，从这里开始：
> 1. 先读 [`ARCHITECTURE.md`](../ARCHITECTURE.md) §6/§7 了解全貌；
> 2. 做 agent 侧 → 按本文 **A 组** 执行，细节全部在 [`AGENT_INTEGRATION.md`](AGENT_INTEGRATION.md)；
> 3. 做 qiye-app 侧 → 按本文 **B 组** 执行，细节全部在 [`QIYE_APP_INTEGRATION.md`](QIYE_APP_INTEGRATION.md)；
> 4. 接口/命令的请求响应形状，一律以 [`API.md`](API.md) 为准；清单字段以 [`SPEC.md`](../SPEC.md) 为准。
> 完成一项就把 `[ ]` 改成 `[x]` 并提交，本文件即进度看板。
>
> 依赖关系：**A 组是地基**（B 组的所有接口都由 A 提供）；C 组（注册表数据）与 A 并行；B 依赖 A1–A6。
> 仓库路径约定：agent = `../totalclaw-agent`，qiye-app = `../totalclaw-qiye-app`，本仓 = `totalclaw-mcp`。

---

## A 组 · totalclaw-agent 改造（M1，地基）

### A1. `mcp_hub` 核心模块
- [x] **A1.1** 已实现 `totalclaw_core/mcp_hub.py`（对标 `tool_hub.py`）：`fetch_registry / search / resolve / plan / install / update / remove / list_installed / check_updates / reload`
  - 注册表 URL：env `TOTALCLAW_MCP_REGISTRY`，默认 `https://gitee.com/jlzdyx/totalclaw-mcp/raw/master/registry.json`
  - 缓存：`$TOTALCLAW_HOME/mcp/registry-cache.json`，TTL `TOTALCLAW_MCP_REGISTRY_TTL`（默认 3600s）
  - 离线回退：注册表不可达且无缓存 → 用 `mcp_presets.PRESETS` 生成伪条目（`source: builtin`）
  - 复用（import，不复制）：`plugin_hub._download_raw / _download_sparse / _verify_files / _signature_gate / is_hub_entry`
- [x] **A1.2** 已实现 `totalclaw_core/mcp_hub_render.py`：`mcp.yaml` → `mcp_servers.<name>` 渲染
  - runtime 选择顺序：显式 `--runtime` > `TOTALCLAW_MCP_ORG` 已设且清单含 `hosted` > `http` > 第一个 `shutil.which(launcher)` 可用的 `stdio`（docker 额外 `docker info`）
  - env 键：默认 `MCP_<NAME_UPPER>_<VAR>`；清单声明 `env_key` 则保留原变量名（27 条种子全部用 `env_key`，零迁移）
  - `auth: header` → `Authorization: Bearer ${MCP_<NAME>_API_KEY}`（与 `mcp_admin._provision_bearer` 同构）
  - 渲染结果必须能通过 `mcp_admin._normalize_server_spec`（写单测保证，见 A6.1）
- [x] **A1.3** 已实现 `totalclaw_core/mcp_hub_lock.py`（对标 `skills_hub_cache_body.HubLockFile`）：
  - `$TOTALCLAW_HOME/mcp/installed.json`：`{name: {id, version, runtime, source, bundle_sha256, installed_at, updated_at}}`
  - `$TOTALCLAW_HOME/mcp/audit.log`：`<ISO8601Z> <action> <name> <source> <verdict>`
- [x] **A1.4** 九步流水线已实现并端到端验证（resolve → gate → download/verify → validate/render → security → write → probe → reload → finalize），每步 `on_log` 回调
  - security 步：`mcp_security.validate_mcp_server_entry` + `package_pin_problem` + `osv_check`
  - write 步：秘密 `save_env_value` → `.env`；`mcp_admin.add_server`；`tools.json` 预填 `mcp/schema-cache/<name>.json`
  - probe 步：复用 `_mcp_config_impl._probe_single_server`；失败 → `set_enabled(False)` + `needs_setup`
  - reload 步：进程内有 MCP loop → `reload_mcp_servers()`；否则交给 `cli.py` 5s 配置监视
  - 门禁：未 `verified` 需 `allow_unverified` 且默认 `enabled=False`；`scan_verdict: block` 永不安装、`ask` 需确认
- [x] **A1.5** `uninstall_mcp_server()` 已实现完整清理：`mcp_admin.remove_server` + `installed.json` 条目 + `mcp/schema-cache/<name>.json` + `mcp-tokens/<name>*.json` + `.env` 中 `MCP_<NAME>_*` 键

### A2. CLI 子命令
- [x] **A2.1** 已实现 `totalclaw_cli/_mcp_hub_impl.py`，9 个子命令全部带 `--json` 与语义化退出码，挂到既有 `mcp` 子命令树（`_main_impl.py` 的 mcp parser）：
  `search / info / plan / install / update / uninstall / installed / status / reload`
  - 全部支持 `--json`（JSON 到 stdout，日志到 stderr）
  - 退出码：`0` 成功 / `1` 错误 / `2` 缺必填 env（`--json` 含 `missing_env[]`）/ `3` 探测失败已保存为 disabled
  - `install` 旗标：`--env K=V ... --runtime ID --yes --no-probe --disabled --allow-unverified --overwrite --json`
- [x] **A2.2** `mcp catalog` 保留可用（`--install KEY` 是既有流程，改成别名会打断脚本），
  改为在命令开头指向能力更全的 `mcp search`；顺带透传其退出码（此前不存在的 key 也退 0）。
  `mcp presets` 仍是离线回退入口
- [x] **A2.3** bash 补全已支持 `mcp <TAB>` 二级子命令，且从安装账本补全已装 server 名

### A3. qiye_api 接口
- [x] **A3.1** 已实现 `totalclaw_qiye_api/mcp_hub_api.py`，11 个端点已挂进 GA 路由表（对标 `skill_shop_api.py`，`build_router()` + `register` 进 `server.py:1454` 的 GA 路由表）：
  - `GET /v1/mcp/registry`（代理+缓存，响应含 `source: remote|cache|builtin`）
  - `GET /v1/mcp/registry/{id}`、`POST /v1/mcp/plan`
  - `POST /v1/mcp/install` → **202** `{job_id, poll_url}`；409 同名作业进行中；422 `{detail:"missing_env", missing_env:[]}`
  - `GET /v1/mcp/jobs`、`GET /v1/mcp/jobs/{job_id}?tail=200`（job 结构见 API.md §②）
  - `GET /v1/mcp/installed`（installed.json + `get_mcp_status()` 合并）
  - `POST /v1/mcp/servers/{name}/update`（202）、`POST /v1/mcp/reload`、`GET /v1/mcp/status`
- [x] **A3.2** `_notify_mcp_change()` 已实现，作业末尾热重载，装完当轮可用：安装/卸载/更新作业末尾执行 `reload_mcp_servers()` + 对热池 agent `refresh_tools()`（对标 `skill_shop_api._notify_skill_change`）
- [x] **A3.3** `DELETE /v1/mcp/servers/{name}` 已改为完整清理（账本+schema-cache+令牌+.env），响应形状兼容
- [x] **A3.4** `MCP_SERVER_MANAGEMENT.md` 已补「3.5 从 MCP 仓安装」一节（10 个端点 + 三个语义化返回），并删掉已过期的「下个会话生效」提示

### A4. 既有 bug 顺手修（清单与行号见 AGENT_INTEGRATION.md §5）
- [x] **A4.1** `cmd_mcp` 已透传退出码（此前返回值被丢弃，`mcp test` 连不上也退 0）
- [x] **A4.2** `_dump_impl.py` MCP 计数已改读 `mcp_servers`（此前读 `config.mcp.servers`，恒为 0）
- [x] **A4.3** `is_mcp_tool_parallel_safe` 已改用 `mcp_naming` 拆分，并保留旧形态兼容历史会话
- [x] **A4.4** `prompt_builder_body.py` 8 处工具名已改双下划线
- [x] **A4.5** `website/docs` 两篇文档共 11 处命名已更新
- [x] **A4.6** `--preset` 已统一：本地补充项 + 内置目录，可用数从 1 → 27

### A4.7（新增，已完成）`mcp_admin` 静默丢配置

- [x] **A4.7** `_normalize_server_spec` 只按白名单挑键，静默丢弃 `timeout` /
  `connect_timeout` / `keepalive_interval` / `tools`（含 include/exclude 过滤）/
  `sampling` / `elicitation` / mTLS 三件套 —— 而运行时 `server_task.py` 与
  `registration.py` 明确读这些。经 `add_server`（以及 `POST /v1/mcp/servers`，
  **qiye-app 的 MCP 面板走的正是这条**）配的这些字段从来没生效过，接口还返回成功。
  `tools.exclude` 尤其要紧：它是把危险工具挡在模型视野外的手段，被静默丢掉
  意味着「以为排除了、实际没有」。已修 + 11 个回归用例。

### A4.8（新增，已完成）两个装上就挂的 preset

- [x] **A4.8** 实跑发现并修复，与已知的 `mcp_fetch` 同类：
  - `mcp_time`：`@modelcontextprotocol/server-time` 在 npm 上不存在，
    上游只发 PyPI 的 `mcp-server-time` → 改用 uvx
  - `mcp_sequential_thinking`：包名少了连字符（应为 `server-sequential-thinking`）

  两者 npx 都是拉不到又不快退，一路挂到 timeout。已同时加进
  `RETIRED_LAUNCH_SPECS`，`totalclaw migrate mcp` 可修存量用户的坏配置。

### A4.9（新增，已完成）离线回退丢凭据声明

- [x] **A4.9** 内置 presets 回退路径下，preset 的 `${VAR}` 凭据引用被丢掉，
  `requires_env` 恒为空 —— 「缺凭据」对离线条目永远算不出来，装上就是个连不上的
  条目。现在会从 `args`/`env`/`headers` 抽取（带默认值的 `${VAR:-x}` 不算必填）。
  26 条内置里 10 条需要凭据。

### A4.10（新增，已完成）域路由把 MCP 浏览器工具整体排除

- [x] **A4.10** `tool_router` 的 web/browser 域前缀写的是 `mcp_playwright_`，
  匹配不到真实注册名 `mcp__playwright__browser_navigate` —— **域收窄时
  Playwright 的 MCP 工具会被整体排除**，而这正是 `test_playwright_mcp_preferred.py`
  自称要防的事。该测试此前通篇用旧名字构造工具，等于在测一个不存在的世界，
  真实问题反而测不出来。已修前缀 + 测试改用 `mcp_prefixed_tool_name` 生成真实名。

### A5. 环境变量与文档
- [x] **A5.1** 6 个 `TOTALCLAW_MCP_*` 已补进 `environment-variables.md`：原文：`TOTALCLAW_MCP_REGISTRY / TOTALCLAW_MCP_API_BASE / TOTALCLAW_MCP_REGISTRY_TTL / TOTALCLAW_MCP_REQUIRE_SIGNATURE / TOTALCLAW_MCP_TELEMETRY / TOTALCLAW_MCP_ORG`，补进 `website/docs/reference/environment-variables.md`
- [x] **A5.2** `doctor` 已加安装账本一致性检查（账本孤儿 / 手工配置 / 可查更新）

### A6. 测试
- [x] **A6.1** `test_mcp_hub_render.py` 10 个用例；44 条真实清单逐条渲染均过 `_normalize_server_spec`：本仓 27 条种子逐条渲染 → 必须通过 `_normalize_server_spec`；`env_key` 保留断言；runtime 选择矩阵
- [x] **A6.2** `test_mcp_hub_install.py` 10 个用例（含篡改拒绝、未审核门禁、探测失败降级、卸载清理）：本地假注册表（http.server）端到端；sha256 篡改必须失败；未 verified 需 `--allow-unverified`；卸载清理完整性
- [x] **A6.3** `test_mcp_hub_api.py` 11 个用例（含 422/409/作业阶段日志/卸载清理）：202 + 轮询、409、422 missing_env、reload 响应形状
- [x] **A6.4** `test_mcp_hub_cli.py` 12 个用例，退出码 0/1/2/3 + `--json` 单对象契约

---

## B 组 · totalclaw-qiye-app 改造（M2，依赖 A1–A3）

### B1. IPC 层
- [x] **B1.1** 已新增 10 个通道（含 STATUS）：
  `QIYE_API_MCP_REGISTRY / REGISTRY_INFO / PLAN / INSTALL / JOB / INSTALLED / UPDATE / RELOAD / STATUS`
- [x] **B1.2** handler 已实现：**一律 `postRaw / getRaw`**（camel→snake 会把 `GITHUB_TOKEN` 折成 `github_token`，参照既有 `QIYE_API_MCP_UPSERT` 的注释）；限流 install=10 / reload=6
- [x] **B1.3** preload 已暴露 10 个方法
- [x] **B1.4** 配额门控已实现（`packages/edition-features/src/mcp-quotas.ts` + INSTALL handler）
  - 沿用 group-quotas 既有约定：`null` = 不限、按 tier 兜底、服务端非 null 覆盖
  - **重装已装过的不占新名额**（否则配额用满时连修都修不了）；取已装列表失败时不拦
  - 9 个单测覆盖 baseline / 合并 / 解析边界 / 重装豁免

### B2. 统一市场页
- [x] **B2.1** 已实现 `renderer/views/McpMarketView.vue`：Tab「市场」（registry 搜索 + 分类 chips + verified 徽标 + 工具数）/ Tab「已安装」（状态卡 ready/connecting/failed/disabled/needs_setup/update_available；操作：启停/更新/卸载/重新探测/OAuth 登录；顶部「重载 MCP」按钮）
- [x] **B2.2** 已实现 `renderer/components/mcp/McpInstallDialog.vue` 四步向导：
  选 runtime（灰掉 `available=false` 并显示 reason）→ `requires_env` 表单（复用 plugin requires_env 渲染器，`secret` 密码框）→ `plan` 预览（脱敏配置块/工具列表/安全结论/覆盖提示）→ install + 轮询 job 逐行日志；422 `missing_env` 回到表单
- [x] **B2.3** 路由 `/mcp` 已加，门控沿用 feature id `mcp-market`
- [x] **B2.4** `McpServerPanel.vue` 已降级为「已安装」页底部的折叠区，并写清何时才该用它
- [x] **B2.5** `PluginsView.vue` 的内存版 MCP 段已替换为指向 `/mcp` 的引导卡（并注明为何迁走）。
  `packages/mcp-market` 与 `feature-handlers.ts` 的 5 个通道**暂留**：直接删有连带风险，
  而用户可见的「两处入口互相矛盾」问题已由引导卡消除。彻底移除见 B2.5.1
- [x] **B2.6** 46 处用户可见文案已包进 `$t()`（带变量改具名参数），en.json 追加 36 条；
  ar.json 未动 —— 不臆造译文，缺项按机制回落原文，留给母语者补

- [x] **B2.5.1** 5 个 handler + 5 个 preload 绑定已移除（确认无 UI 引用后）；
  `packages/mcp-market` 暂留并标注 `@deprecated` —— packaging-manifest 仍用同名模块开关做裁剪

### B3. 企业与多账号
- [x] **B3.1** 已写成回归测试而非手工验证（agent 仓 `test_mcp_hub_account_isolation.py`，5 项断言：
  配置 / 安装账本 / 状态目录 / **目录缓存** / 卸载互不影响）。
  目录缓存那条尤其要紧：企业私有目录混进别人的缓存等于越权可见
- [x] **B3.2** `?org=` 已按请求透传（IPC 从 payload 或登录态取）。
  **`extraEnv` 注入 `TOTALCLAW_MCP_ORG` 这条行不通并已放弃**：qiye-api 进程在登录之前
  就已经起来了，那时还不知道 org 是谁，注入空值反而会让 mcp_hub 误以为配了托管
  而去替换端点里的 `{org}`。
- [ ] **B3.2.1**（M3 联动，待平台就绪）付费/私有条目的 `bearer_token` 传平台 JWT
  - 做的时候注意两处（2026-08-23 查过代码）：
    1. qiye-app 的 `QIYE_API_MCP_INSTALL` 是 **`c.postRaw('/v1/mcp/install', payload)` 整包透传**，
       而 agent 的 `InstallRequest` 是 pydantic 模型、**不认的字段会被静默丢掉**。
       只在前端加 `bearerToken` 而忘了加模型字段的话，token 会无声消失，
       表现是厂商侧 403，查起来完全看不出是自己把它丢了。
    2. `mcp_hub._download_entry` 走的是 `plugin_hub._download_raw`，那条路**没有**
       带鉴权头的入口。skill-shop 的付费下载是另起一条 httpx 调用
       （`skill_shop_api.py` 第二步），MCP 这边要照那个形状单开一条，
       不要去改 `_download_raw` —— 它是 plugins/tools/skills 共用的。

---

## C 组 · 本仓注册表数据（与 A 并行）

- [x] **C1** 包版本全部 pin 到实测最新稳定版，`--strict` 已零警告，CI 已切 `--strict`
  - 顺带修出两个继承自 agent presets 的真 bug：
    `@modelcontextprotocol/server-sequentialthinking` 少了连字符（npm 上不存在）；
    `@modelcontextprotocol/server-time` 在 npm 上根本没有，该服务器是 PyPI 的
    `mcp-server-time`，runtime 已从 npx 改为 uvx —— 正是 agent `RETIRED_LAUNCH_SPECS`
    要防的「包不存在 → 挂到超时」那类问题
- [x] **C2** `scripts/probe_server.py`：真实启动 → `list_tools` → 写回 `tools.json` + `security` 块
  - 注入扫描 10 条模式（与 agent `helpers.py` 同源），命中即把 `scan_verdict` 置 `warn`
  - 子进程 env 白名单，与 agent 的做法一致；`--dry-run` / `--skip-auth` / `--runtime`
  - 自研服务器自动跳过（其 `tools.json` 由 `gen_manifests.py` 从实现直接生成）
  - 已实跑 5 个上游条目：`mcp_time`(2) `mcp_fetch`(1) `mcp_sequential_thinking`(1)
    `mcp_memory`(9) `mcp_everything`(13)，全部连通、无注入嫌疑
  - 这轮实跑同时验证了 C1 的两处包名修复确实可用（原规格会挂到超时）
- [x] **C2.1（工具就绪部分）** `probe_server.py` 加了 http 支持——此前只探 stdio，
  http 型一律跳过，于是「有凭据就能补跑」根本没有工具可用。同时把 MCP SDK 的
  `ExceptionGroup: unhandled errors in a TaskGroup` 拆开报根因：401 缺凭据、
  404 端点没了、超时，这三种此前长得一模一样，没法排查。
- [x] **C2.1（鉴权方式部分）** 把全部 59 个 http 条目挨个发请求，看 401 里的
  `WWW-Authenticate` 有没有 `resource_metadata` —— **41 个支持标准 MCP OAuth**。
  这些**根本不需要预置凭据**：清单改成 `auth: oauth` 后，用户装完跑
  `totalclaw mcp login <名>` 浏览器授权即可。已改 36 个（渲染后 `missing_env` 为空）。
  另外 4 个（fanruan / youshu / picset / gangtise）本来就有明确的 `${VAR}` 静态凭据，
  有 key 直连更省事，没动；fadada_richee 的 OAuth 证据只是主机级 well-known
  且指向别家产品那条路径，不够硬，也没动。

  **此前我把这 41 个都归进了「等厂商凭据」，是错的** —— 401 不等于「要一把预置的 key」，
  得看它질质询里说的是什么。
- [x] **C2.1（凭据获取路径）** 上游每个连接器还带一份 `token-schema.json`，
  里面是厂商自己写的说法：去哪个页面、点哪个菜单、复制哪一项，以及申请地址。
  **我此前整轮都没打开过这个文件** —— 于是 registry 里的凭据说明是生成器套出来的
  同义反复（「XX 所需的 XXX_API_KEY」/「请输入 XXX_API_KEY」）。用户看了还是不知道
  去哪儿弄，凭据填不上，那个条目就等于装不了。
  已并进 **20 个条目、21 条凭据**：`description` 换成厂商原话，`prompt` 换成
  厂商的输入提示，新增 `doc_url` / `doc_label`（SPEC §2.3 已补进规范）。
  索引生成器也一起改了 —— 它此前把 `doc_url` 过滤掉，而 qiye-app 读的正是索引，
  不改就等于白做。qiye-app 的安装向导已渲染成链接，3 个用例覆盖。
  顺带补了 `weisheng_scrm` 漏声明的 `SCRM_APP_KEY`、`opendata` 的
  `REGION_INSIGHT_API_KEY`（匿名能列工具，真调用要 key，不声明的话用户装完
  一调就失败且不知为何）。
- [x] **C2.1（stdio 那批，2026-08-23）** 此前只扫了 http，**stdio 从没实探过**。
  装包实探后 **18 个条目拿到真实工具清单**，有工具的条目 36 → 54，工具总数 827。
  过程中修出 5 个「装上必挂」的条目 + 2 个我自己的 bug：
  - **`${VAR:-default}` 语法 agent 根本不支持**。SPEC 第 57 行却写着「允许」——
    规范承诺了消费方做不到的事。agent 的 `utils.interpolate_env_vars` 正则是
    `\$\{([^}]+)\}`，会把 `MCP_FS_ROOT:-/tmp` **整个当变量名**去查，查不到就原样
    留着，服务器拿到一串字面量当路径/目录名，起手就挂。
    `mcp_filesystem` 与 `mcp_sqlite` 两条中招；导入脚本当年也被这语法截断，
    在 `mcp_sqlite` 的 optional_env 里留下过一个残缺的 `default: ${HOME`。
    已改成显式变量 + 必填。`mcp_filesystem` 这样反而更安全：沙箱根目录本来就该
    让用户自己选，静默默认 `/tmp` 等于替用户决定了哪些文件可被模型读写。
  - **4 个包与新版 MCP SDK 不兼容**（`mcp_sqlite` / `blender` / `docker` / `dy_xhs`）：
    `ModuleNotFoundError: mcp.server.fastmcp` 或 `'Server' object has no attribute
    list_prompts/list_resources`。都加 `--with mcp==1.19.0` 钉住能用的 SDK。
    `mcp-server-sqlite` 的最新版就是出问题那版，没有更新的可换。
  - **`ai_hive` 已删除**：`@infimind-next/ai-hive-mcp` 起手就打印「尚未连接
    AI-HIVE，请在 WorkBuddy 中重新连接」，是别家产品的专属客户端，在我们这儿
    永远起不来 —— 而清单里写的是 `requires_env: []`（无需凭据，装了就能用）。
    条目数 115 → 114。
  - **`scripts/probe_server.py` 不展开 args 里的 `${VAR}`**（只展开了 url 与 env）。
    agent 侧是对整个 server 字典递归展开的，探测与真实启动行为不一致 ——
    这个方向的偏差尤其糟：探测过了，装上却挂。已修。
- [ ] **C2.1（2026-11-27 进展）** 注册表扩到 650 条后，547 条没有工具清单：
  - 不需要凭据的 284 条逐个实探：**175 条已补齐工具清单**（注入扫描命中 3 条，人工复核均为误报：output_firewall / wireshark 是检测外传的防护工具，openhire 是要求如实报告测量值；其中 openhire 的描述原文会触发 `--scan-registry` 门禁的「do not tell the user」规则，为不放宽门禁，其工具清单暂不入库）；**108 条起不来**（88 连接关闭、14 超时、其余鉴权 / 需本机 IDE），属清单漏声明凭据或包本身有问题，另行排查（C2.2）
  - 需要凭据的 263 条（OAuth 68 / Bearer 21 / 环境变量 174）：申请清单见 [credentials-needed.md](credentials-needed.md)，等凭据
  - 原记录：还有 60 个条目没有工具清单，都要真凭据：
  - **http 型 40 个**：2026-08-23 全量匿名探过，**40 个全部 401**，无一能匿名列工具。
    这一项不是「还没探」，是**确实要凭据**——别再重跑匿名探测了。
  - **stdio 型 3 个**（`sentry` 已修好并实探到 9 个工具，见上）—— **2026-11-12 这三个条目已从注册表删除**：
    一直没有扫描结论（厂商闭源包看不到源码 / 要本机已装的产品目录），不能确认无毒，按负责人要求删除，
    条目数 560 → 557，剩下没有扫描结论的 57 条全是远程网址类（本机不落任何代码）。删除只是不再上架；
    已经装过的用户本机不会被自动停用（只有 `scan_verdict: block` 才会），要连已装的一起停得改成下架。以下是删除前的记录：
    - `infimind_ecommerce_image` —— Unauthorized，要厂商凭据；
    - `matrixmedia` —— 要本地已装好的产品目录（`MATRIXMEDIA_DIR`）；
    - `duoguan_fengchao` —— 报的是 **`Runtime manifest 缺少受信任的 Ed25519 签名`**，
      挂在签名校验那一步而不是鉴权那一步。它是个「校验+缓存+启动真正 runtime」的
      启动器，签名从哪儿来、给不给凭据就能拿到，**没有凭据无法判定** ——
      有可能和已删掉的 `ai_hive` 一样是厂商专属启动器。拿到凭据先验这一条。
  - 拿到凭据后：`export <VAR>=… && python3 scripts/probe_server.py <名>`；
    OAuth 型先 `totalclaw mcp login <名>`。去哪儿申请，registry.json 里就有。

- [x] **C3** Ed25519 签名脚本 `scripts/sign_registry.py`（`--keygen` / `--sign` / `--verify`）
  - 已实测完整链路：生成密钥 → 签名 → 验签通过 → 篡改一个字段后验签**正确失败** → 恢复后再通过
  - 私钥只从 `MCP_REGISTRY_SIGNING_KEY` 或库外文件读，keygen 默认写到 `~/.totalclaw-mcp-keys`
    并置 600；`.gitignore` 已挡 `*.ed25519.key`
  - 为什么需要签名：`files[].sha256` 只保证「下载到的文件没被中途改」，
    但分发点整体被替换时索引和文件会被一起换掉；签名把信任根挪到私钥上
- [x] **C3.1（CI 验签部分）** CI 加了验签步骤：`registry.pub` 存在才跑，不存在就跳过。
  这样公钥一进库就自动开始把关，不用再改 CI。已用一次性密钥实测完整链路——
  keygen → sign → verify 通过 → 改一个字段后 verify **正确失败** → 清理干净。
- [ ] **C3.1（剩余）** 生成正式密钥对、私钥进 CI secret、提交 `registry.pub`。
  **这一步该由你做，不该由我做**：私钥一旦经我手就等于泄露过，签名的意义就没了。
  三条命令：
  1. `python3 scripts/sign_registry.py --keygen`（私钥默认写到库外 `~/.totalclaw-mcp-keys`，权限 600；
     公钥写到 `registry.pub`）
  2. 私钥内容存进 CI secret `MCP_REGISTRY_SIGNING_KEY`，然后**把本地私钥文件删掉**
  3. `git add registry.pub && git commit` —— 提交后 CI 的验签步骤自动生效
  注意：`registry.json` 每次重新生成后都要重新签名，否则验签会失败。
- [x] **C4.1** 推送 Gitee 仓库 `jlzdyx/totalclaw-mcp`（分支 **master**，与 `registry.json` 的 `raw_base` 路径一致）
- [x] **C4.2（仓库侧已备好）** 分发通道 **决定：转公开**（2026-08-23 你定的）。
  仓库侧该做的都做完了，**只差你在 Gitee 网页上翻那个开关**：
  Gitee → 仓库 → 管理 → 仓库设置 → 开源。翻完 `mcp_hub` 就能匿名拉 raw，
  agent 与 qiye-app **零改动**（`raw_base` / `git_sparse` 一直就是公开路径的形态）。
  - 公开前的体检（已做）：
    - **工作区与全量 git 历史都扫过凭据**（`ghp_` / `github_pat_` / `sk-` / `AKIA` /
      PEM 私钥 / `xox*`）——**零命中**。仅有的两处是文档占位 `ghp_xxx` 与
      `servers/tests/test_engine.py` 里的脱敏标记表，都不是真凭据。
    - 曾提交过的「敏感文件名」也查过：只有 `bugly_token/mcp.yaml`（条目就叫这名）
      与 `engine/token_exchange.py`（一种鉴权方式），无 `.env` / `.key` / `.pem`。
    - 补了根目录 `LICENSE`（Apache-2.0，与 `servers/pyproject.toml` 早已声明的一致）。
      **公开前想换别的授权，现在改还来得及。**
    - 补了 `NOTICE`：26 个厂商图标、条目所指向的第三方服务、厂商名称与产品名
      **都不在 Apache-2.0 的授权范围内**。没有这条，一个 Apache-2.0 的仓库看上去
      像是在转授权别人的商标。
  - 翻开关之后建议顺手验一下：
    `curl -sI https://gitee.com/jlzdyx/totalclaw-mcp/raw/master/registry.json | head -1`
    —— 现在是 403，公开后应为 200/302。届时桌面端市场页的 `source` 会从
    `builtin`（离线内置 26 条）变成 `remote`（115 条），厂商图标也会一起显示出来。
- [x] **C4.3** CI（`.github/workflows/ci.yml`）：
  - `gen_registry.py --check --strict`（版本未 pin 直接失败）
  - `totalclaw-mcp-server --check` + `pytest`
  - 生成物一致性：跑完 `gen_manifests.py --force` 与 `gen_registry.py` 后必须无 diff，
    防止改了 servers/ 却忘了重新生成清单
- [x] **C5（英文描述部分）** pack 规范加 `description_en`，21 条自研条目全部补齐；
  `gen_manifests` 改为 `description` 取英文、`description_zh` 取中文 —— 此前两处都填中文，
  英文界面上就只能看到中文
- [x] **C5.1（机制部分）** 图标链路打通：
  - `gen_registry.py` 新增 `icon` 投影 —— 此前 SPEC 写了 `icon.svg|png` 这个可选文件，
    但索引里**根本没有这个字段**，也就是说就算真放了图标客户端也找不到它
  - 读接口 `GET /api/mcp/servers/{name}/icon`：有自带图标发真的（`X-Icon-Source: file`），
    没有就发按「首字 + 分类取色」生成的字母块（`generated`）。全库 115 条跑过，不 500
  - 真图标放进条目目录即刻生效，客户端零改动
  - qiye-app 市场卡片已用上（`utils/mcpIcon.ts` + `McpMarketView.vue`，11 个用例）。
    算法与 `icon.py` **逐字一致**，两个仓的测试各钉一份期望值：桌面端走 qiye_api
    拿目录、不请求读接口，两边算出不同颜色的话同一个条目会显示成两个颜色。
    明度微调刻意用字符码求和而不是哈希 —— 就是为了 Python 与 TS 都能一行写对
  - 桌面端**不渲染指向 `raw_base` 的 `<img>`**：仓库是私有的，匿名拉 raw 是 403，
    挂一个必然裂掉的图比没有更糟。等 C4.2 定了分发通道再接
- [x] **C5.1（素材部分，2026-08-23 你定的：抓下来收进目录）** `scripts/fetch_icons.py`
  从各条目的 `homepage` 抓**厂商自己站点上**的图标，抓到 **26 个**。
  - 三个必须挡的坑：① 55 个条目的 homepage 指向 github/gitee/npm/cnb 这类代码托管站，
    照抓会给一半条目贴上 GitHub 的猫 —— 目录看上去像所有东西都是同一家的，比没有更糟，
    一律跳过；② 国内站大量用 `.ico`（多帧容器），转 PNG 取最大帧；
    ③ 有的站把图标内联成 `data:` URI（bugly），单独解。
  - 来源逐条留痕：`registry/icons.json` + `registry/ICONS.md`（来源 URL + 抓取日期），
    并与磁盘对账。**第一版把上一轮的记录冲掉了**（26 个图标只剩 9 条记录）——
    图标是第三方商标，「这张从哪儿来」正是这个文件存在的全部理由，已改成累积写。
  - 授权边界写进根目录 `NOTICE`：这些图标不在本仓 Apache-2.0 的范围内。
- [x] **C5.1（顶级域回退，2026-08-23）** 抓到的图标 **26 → 43**。
  上一轮记的原因「homepage 指向 API 主机而非产品站」是对的，但我只写了没去修。
  清单里的 `homepage` 大多写的是 MCP 端点或文档地址（`mcp-center.wps.cn`、
  `apigateway.gaodun.com`、`api.gildata.com`…），主页上根本没有产品图标 ——
  加一跳「退到顶级域再试」就多抓到 18 个。
  - 两个必须挡的：① **伞状域名**不回退（`stockbuddy.qq.com` 退到 `qq.com` 拿到的是
    QQ 的企鹅，产品是腾讯自选股）；② **第三方基础设施的标**要过滤 ——
    `shanglv_mcp_gateway` 的网关挂着 Keycloak 登录页，抓到的是
    `.../keycloak.v2/favicon.svg`，挂上去等于给商旅贴了 Keycloak 的标。
    已按关键词过滤（keycloak/auth0/okta/swagger/wordpress…）并复核了全部 43 个文件。
- [x] **C5.1（www 那一跳，2026-08-23）** 图标 **43 → 48**。
  上一条说「多数站点连不上」也只对了一半：裸顶级域确实不通，但**加上 `www.` 就通** ——
  `mozlen` / `tcredit` / `gangtise` / `morningstar` / `dknowc` / `microdata-inc` /
  `kuaicha365` 七个主机都是这样。我的顶级域回退漏了这一跳，于是把「只在 www 上服务」
  误判成了「站点不可达」。补上后又抓到 5 个。
  （先用 curl 复核过：这些主机 curl 也连不上裸顶级域，所以不是 httpx 的问题；
  但 `www.` 前缀 curl 立刻 200 —— 是我少试了一种写法，不是网络的锅。）
  48 个文件逐个核过魔数，也确认没有混进第三方基础设施的标。
- [x] **C5.1（父域回退 + 体积上限，2026-08-23）** 图标 **48 → 51**。
  伞状域名那 3 条我之前一刀切禁掉了回退 —— 但**产品站往往正好在中间那一层**：
  `sse.qidian.qq.com` → `qidian.qq.com` 是腾讯企点自己的站（favicon 路径里就带
  qidian），再往上才是 `qq.com`（QQ 的企鹅）。改成逐层剥标签、撞到伞状域名才停，
  `tencent_qidian_cs` / `tanyuan_assistant` / `westock_mcp` 三条都补上了。
  - 顺带发现一个会拖垮 bundle 的问题：`stockbuddy` 的 `<link rel=icon>` 指的是
    `/logo.jpg`（165 KB），jpg→png **撑成 1.3 MB**。`MAX_BYTES` 卡的是下载的字节，
    卡不住转换后的。转换统一缩到 256px 边长并复查体积后，51 个图标合计 367 KB、
    最大 59 KB。加了用例守住这条（`test_icons_stay_small`）。
- [ ] **C5.1（剩余）** 2026-11-26 换网络重跑：`unreal_engine` 补到（epicgames.com 自家图标），图标 51 → 52；`tec_do` / `fyopen_lawsearch` / `mzl_trademark` / `shanglv_mcp_gateway` / `lexiang` / `gildata` 站点现在都能连上，但站上确实没有图标。原记录：确实抓不到：站点与 www 都不通的
  （`cjbdi.com` / `lexiang-app.com` / `tec-do.cn` / `epicgames.com` / `yql.net` —— 
  **换个能连通的网络重跑 `scripts/fetch_icons.py` 可能还能补**），
  以及 `gildata.com` / `mozlen.com` 等站上确实没有任何图标来源的。
  在此期间它们回落字母块，界面不会开天窗。

---

## 验收（端到端场景，全过即对接完成）

> 已脚本化：`python3 scripts/acceptance.py`（每项独立临时 `TOTALCLAW_HOME`，不碰真实配置，
> 可随时重跑）。手工点一遍的问题是下次改动后没人会再点。
> 最近一次：**通过 6 · 失败 0 · 需人工 1**。

- [x] **V1** CLI 装上并在 `installed` 可见（本环境探测失败→按设计置 disabled，退出码 3 也算通过）
- [x] **V2** 缺 env 退出码 2 + `missing_env` 列表正确
- [x] **V3（组件行为部分）** qiye-app 补了两份组件测试，共 **36 个用例**
  （`McpInstallDialog.test.ts` 18 + `McpMarketView.test.ts` 18），用
  `@vue/test-utils` + happy-dom，不需要 Electron。盯的是错了不会当场报错的那些：
  - 凭据键名映射（清单 `name` → `.env` 的 `env_keys[name]`）—— 反了的话凭据会落到
    没人读的键下，安装照样「成功」，然后连不上
  - 空值/纯空格不提交，否则会把已有凭据覆盖成空串
  - 422 `missing_env` 回到填凭据那步，不是弹红条把人卡在预览页
  - 轮询定时器在关闭与卸载时都必须停干净
  - 离线降级提示、卸载前确认（文案要讲清凭据会一并清掉）、「更新」只对注册表条目开放
- [x] **V3（自动化部分）** 真 Electron 端到端已落成脚本：qiye-app 仓
  `apps/desktop-shell/e2e/mcpMarket.e2e.mjs`（`pnpm e2e:mcp`）。用 Playwright 的
  `_electron` 拉起 **dist 构建**（不是源码），等主窗口、等 qiye-api 子进程就绪，
  再走真 IPC 调 `mcpRegistry()`。
  单元测试结构上看不见这一层：渲染层用例把 `window.electronAPI` **mock 掉了**，
  agent 侧 `test_mcp_hub_api.py` 用 TestClient **直接打路由**——
  「路由有没有真挂在跑着的那个进程上」两边都绕过去了。
- [x] **V3（真机接线已通过）** 2026-08-23 跑通：**5 过 0 挂**。
  ✓ 启动进主窗口 · ✓ preload 导出全部 15 个 MCP 函数 · ✓ `/mcp` 路由挂载 ·
  ✓ `mcpRegistry()` 取回目录 · ✓ 24 张卡片 24 个图标。
  - 修的是两处**只有真机才现形**的问题：
    1. submodule 停在 `699569fae`，那个提交里没有 `mcp_hub_api.py` → 404。
       已 bump 到 `aa47cd5ff`（0.66.53-core）并同步 `check-agent-pointer.mjs` 的
       EXPECTED_VERSION/SHA。丢的 6 个提交逐条核过：5 个是 merge，唯一实质的
       `2aea6758c` 是 agent 仓自己的流水线模板，不随包发出。
    2. **bump 了 submodule ≠ 跑着的 agent 变新了**：上游 wheel 的 `packages.find`
       不含 `totalclaw_qiye_api`（RECORD 里 0 个文件），那个包是构建脚本单独 cp 进
       site-packages 的，而 `setup:totalclaw-agent` 见 venv 已存在就整段跳过。
       坑记在 e2e 脚本头部。
  - 顺带修了一处误导文案：这种 404 此前落到「请稍后重试」，重试一万次也不会好。
- [x] **V3（剩余，2026-11-26 已自动化跑通）** 用 E2E 旁路模拟登录 + `TOTALCLAW_USER_DATA_DIR` 隔离，真 Electron → IPC → qiye-api → agent 全链路 13/13 通过：远程注册表 650 条、缺凭据 422 拦下、block 条目拦下、uvx（ancestry / mcp_time）与远程 Bearer（alphavantage）装上即启用并连上、热重载、卸载清干净、连接器配置里只有 `${…}` 占位。跑法见 memory「桌面端 MCP 端到端 V3」。过程中修出 3 个真 bug，见 F16–F18。原记录：
  脚本不持有账号，走不到那一步。目前目录取的是 `source=builtin`（26 条离线内置），
  C4.2 那个开关翻完会变成 `remote`（115 条），届时值得再人工走一遍完整安装。

- [x] **V4** 篡改 sha256 被拒于校验阶段，config.yaml 无残留
- [x] **V5** 卸载后 config.yaml / .env / installed.json / schema-cache 全干净
- [x] **V6** 断网时 `source=builtin`，内置目录仍可搜可装
- [x] **V7** 双账号互不可见（A 装的 B 看不到）

---

## D 组 · 自研 MCP 服务器实现（`servers/`）

> **方向**：把这些连接器**在本系统里实现一遍**，让 agent / qiye-app 用我们自己的服务器，
> 不依赖任何第三方托管端点。能力清单取自 WorkBuddy 连接器目录（126 个），
> 其上游端点配置仅作为「背后是哪家 API」的佐证，不作为实现。
>
> 实现方式二选一（见 [PACKS.md](PACKS.md)）：
> - **声明式 pack**（绝大多数）：`servers/totalclaw_mcp_servers/packs/<name>.yaml`，零代码
> - **原生服务器**（有状态协议）：`servers/totalclaw_mcp_servers/native/<name>.py`
>
> 每完成一个：`totalclaw-mcp-server --check <name>` → `scripts/gen_manifests.py --force`
> → `scripts/gen_registry.py` → 勾选。

### D0. 引擎与骨架

- [x] **D0.1** REST→MCP 引擎：pack 规范、模板渲染、鉴权、响应裁剪、脱敏（`servers/totalclaw_mcp_servers/engine/`）
- [x] **D0.2** 令牌交换（`token_exchange`）+ 进程内过期缓存 —— 企业微信/飞书/钉钉必需
- [x] **D0.3** 业务错误码检查（`response.error_field`）—— 国内 API 常见的 `HTTP 200 + errcode!=0`
- [x] **D0.4** 原生服务器装配层（`native_server.py`）与模块契约
- [x] **D0.5** CLI：`totalclaw-mcp-server <name> | --list | --check | --describe`
- [x] **D0.6** 打包：`servers/pyproject.toml`，控制台脚本 `totalclaw-mcp-server`
- [x] **D0.7** 测试：31 个用例，含类型保留、缺参、业务错误码、令牌缓存、脱敏（`servers/tests/`）
- [x] **D0.8** `scripts/gen_manifests.py`：从实现自动生成 registry 清单 + `tools.json`
- [x] **D0.9** CI 三个 job：registry（`--check --strict`）、servers（pack 校验 + pytest +
  生成物一致性）、acceptance（V1–V7；拿不到私有 agent 仓时降级为 warning 而非失败）
- [x] **D0.10（发布前验证已完成）** wheel 构建正常（18 pack + 3 原生 + 控制台脚本齐全），
  干净 venv 安装并真实 MCP 握手通过。**实际 PyPI 发布需凭据，留给有权限的人执行**：
  `python -m build --wheel servers && twine upload dist/*`
  - 验证时撞出一个真实的依赖声明错误：`mcp>=1.10` 放行了 2.0，而 2.x 重做了低层
    Server API，装完直接起不来。已改 `mcp>=1.10,<2`，并加 CI `clean-install` job 守住

### D1. 连接器实现进度（126）

按**真实可达性**分层，而不是把 126 项都挂成待办 —— 其中相当一部分要么上游本就不是 MCP，
要么文档需登录/商业授权，硬写只会产出 404 的假 pack。

#### A · 已实现（20 个连接器 → 19 个自研服务器）

- [x] **agentkey** AgentKey — 已实现 `web（抓取部分）`
- [x] **baidu-netdisk** 百度网盘 — 已实现 `baidu_netdisk`
- [x] **canva** Canva可画 — 已实现 `canva`
- [x] **canva-ai** Canva可画 — 已实现 `canva`
- [x] **cloudbase** 腾讯云 CloudBase — 已实现 `tencent_cloudbase`
- [x] **dingtalk** 钉钉 — 已实现 `dingtalk`
- [x] **feishu** 飞书 — 已实现 `feishu`
- [x] **github** GitHub — 已实现 `github`
- [x] **jiandaoyun** 简道云 — 已实现 `jiandaoyun`
- [x] **jinshuju** 金数据 — 已实现 `jinshuju`
- [x] **linear-mcp** Linear — 已实现 `linear`
- [x] **moka** Moka HR 智能体 — 已实现 `moka`
- [x] **netease-mail** 网易邮箱 — 已实现 `imap_mail`
- [x] **notion** Notion — 已实现 `notion`
- [x] **qcc-company** 企查查 — 已实现 `qcc`
- [x] **qq-mail** QQ邮箱 — 已实现 `imap_mail`
- [x] **tapd** TAPD — 已实现 `tapd`
- [x] **tencent-map** 腾讯地图 — 已实现 `tencent_map`
- [x] **tyc-mcp** 天眼查 — 已实现 `tianyancha`
- [x] **wecom** 企业微信 — 已实现 `wecom`

> **一处扫描漏项（用户指出后补的）**：我此前只 glob 了 `connectors/*/mcp.json`，
> 但 126 个连接器里有 26 个用的是 `cli.json`、2 个只有 `token-schema.json`。
> 那 28 个我当时按元数据记成了「上游是 CLI 封装而非 MCP，不在本仓范围」。
>
> **这个结论下早了。** 向日葵就是反例：WorkBuddy 接的是 `@aweray/awesun-cli`，
> 但贝锐自己发了 MCP server（客户端自带的 `awesun-mcp-server`）。
> 「某个平台用 CLI 接的」推不出「这家没有 MCP」。
>
> 已把 21 家 CLI 型连接器逐家在 npm 上查了一遍官方 MCP 包，另外补回两个：
> `awesun`（30 个工具，实探）与 `cnb`（官方 `@cnbcool/mcp-server`）。
> 其余 18 家没搜到官方 MCP 包；`lovrabet` 有包但没 readme 没仓库，
> 不知道参数与变量就写不出正确清单，按老规矩不猜，只记为线索。

#### B · 厂商自有 MCP 端点（66 已收录 / 4 阻塞）

**这一节此前的判断是错的，已纠正。** 原先写的是「73 项待厂商开发者账号」，
前提是每家都得拿到 REST 契约、自己再实现一遍。实际不需要：**这些厂商自己就跑着
MCP 服务器**——`apim-gateway.pkulaw.com`、`openapi.gangtise.com`、`openmcp.lingxing.com`
……70 个端点全是厂商自有域名，没有一个是中间平台的网关（域名归类见
`scripts/import_vendor_mcp.py --audit`）。

厂商已经把 REST 包成 MCP 了，就没有「再实现一遍」的东西可写：REST→MCP pack 要的
正是那层被包起来的 REST 契约。**指向厂商端点是这里唯一正确的做法**，而这跟「下载
别家的东西」是两回事——连的是厂商，不是任何中间平台。

56 项已由 `scripts/import_vendor_mcp.py` 转成清单落地。转换时做了四处规整，都不是
照抄：

| 规整 | 为什么 |
|---|---|
| 丢弃 `X-Request-Source: workbuddy` 一类请求头 | 照抄等于冒充别家产品向厂商网关发请求 |
| npm 包钉到确切版本（`@latest`、`^1.0.8`、无版本各一例） | 装什么版本必须确定，否则今天能用明天可能就变 |
| 去掉 `--registry=registry.npmmirror.com` | 把供应链信任转移到镜像方；包在官方源上有 |
| 描述里的别家产品名换成中性说法 | 目录是给我们的用户看的，指名别家既不准也误导 |

**14 项阻塞**，每项的具体理由已写在下面各条后面，四类：

- **他方专属路由（3）** —— URL 里带着别家产品名。原本 6 项，**把那段标识去掉后
  实测有 3 家存在通用入口**：`bizveris.kuaicha365.com/mcp`（去掉 `?source=` 直通，
  已探到工具）、同域的 `law_agent/mcp`（同样直通）、`claw.richee.cn/claw-api/mcp`
  （401，端点在、要 token）——这三家已改用通用地址收录，不占用别人的路由。
  剩下 3 家（wind、fenbi、wisenote）通用路径实测确为死路，**已试过的变体记在这里，
  别再重试**：`mcp.wind.com.cn/mcp`、`/mcp/`、`/vserver/mcp/` 全 404；
  `market-api.fenbi.com/mcp`、`/open/mcp` 全 404；`100wiser.com/mcp` 405、
  `/wisenote/meeting/mcp` 404、`/api/wisenote/meeting/mcp` 405。
  **要接得自己去和厂商申请一条独立路由。**
- **sse 传输（1）** —— agent 只支持 stdio 与 streamable-HTTP（SPEC.md §runtimes）。
  原本 5 项，**实测把路径末段 `/sse` 换成 `/mcp` 后有 3 家是通的**（opendata 直接连上并探到
  6 个工具；finenter、xingtu-claw-risk 返回 401 —— 端点在、说 streamable-HTTP，只差凭据），
  已改用 http runtime 收录。**proboost 第一次判 404 是我试错了路径**——它的 sse 路径是
  `/mcp-servers/oauth/<名>/sse`，我把 `oauth` 当成了固定段，实际那是 OAuth 流程的子路径；
  按平台约定 `/mcp-servers/<名>/mcp` 再试就直通了，已探到 84 个工具。
  只剩 zfs-fssc-ai，它本就是演示主机。
  「上游写 sse」不等于「只有 sse」，值得先探一下再判死；探的时候路径也别照抄整段。
- ~~平台身份鉴权~~ —— **这一类我判错了，已清零。** 我只看上游的 `auth_mode: server-side`
  就下了结论，没实测。实际上那个字段说的是上游平台自己怎么接的，不代表端点只认它：
  kdocs 匿名就能连（258 个工具），tdx 返回的是标准 MCP OAuth 发现（用 `auth: oauth` 即可）。
  **教训：凭元数据字段推断可用性，不能代替发一个请求。**
- **非生产主机（1）** —— `test.nges.qq.com`，测试环境不进目录。同域生产写法 `nges.qq.com` 连不上。

  > **探测时注意本机 DNS**：这台机器上 `dig` 对任何域名都返回 `198.18.x.x`（代理的
  > fake-IP 段），所以「解析得到」不代表主机存在，「连不上」也不是 DNS 的问题。
  > 我一开始据此写过「DNS 解析不了」，是错的 —— 判可达性要看实际连接结果
  > （`000` 是连不上，`404` 说明主机在、只是路径不对）。同一个坑之前在 SSRF 守卫
  > 上也踩过（`TOTALCLAW_MCP_WEB_ALLOW_PRIVATE` 那个开关就是为它加的）。

已收录条目的 `security.scan_verdict` 一律是 `unscanned`：没有凭据就连不上、
探不到工具列表，也就扫不了注入。有凭据的环境里跑 `scripts/probe_server.py` 补齐。

要给某家写**自研 pack**（而不是指向其端点）时：照 [PACKS.md](PACKS.md) 写即可，
**引擎无需改动**——八种鉴权已覆盖 bearer / header / query / basic / 令牌交换 /
签名 / 腾讯云 TC3。端点从哪儿取见 PACKS.md「怎么拿到可信的端点」。

- [x] **ai-hive** AI-HIVE —— 厂商自有端点，收录为 `creative/ai_hive`
- [x] **archive-hospital-mcp** 腾讯健康全周期管理平台 —— 厂商自有端点，收录为 `office/archive_hospital_mcp`
- [x] **bazhuayu** 八爪鱼 —— 厂商自有端点，收录为 `web/bazhuayu`
- [x] **bugly-token** Bugly 质量概览（上游 auth_mode=token） —— 厂商自有端点，收录为 `infra/bugly_token`
- [x] **camscanner-mcp** 扫描全能王 —— 厂商自有端点，收录为 `creative/camscanner_mcp`
- [x] **chuhaijiang** 出海匠 —— 厂商自有端点，收录为 `biz/chuhaijiang`
- [x] **cisp-mcp** 水滴征信（上游 auth_mode=token） —— 厂商自有端点，收录为 `infra/cisp_mcp`
- [x] **dcs-cloud** DCS Cloud（上游 auth_mode=token） —— 厂商自有端点，收录为 `infra/dcs_cloud`
- [x] **dknowc-mcp** 深知可信工作台 —— 厂商自有端点，收录为 `data/dknowc_mcp`
- [x] **duoguan-fengchao** 夺冠蜂巢（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/duoguan_fengchao`
- [x] **edgeone-pages** EdgeOne Makers — 已实现 `tencent_edgeone`（站点/域名/刷新预热）
- [x] **ezjoin-meeting** EzyJoin智慧会议 —— 厂商自有端点，收录为 `comm/ezjoin_meeting`
- [x] **fadada-richee** 法大大睿契 —— 上游路径末段是他方产品名，去掉后 `claw-api/mcp` 实测存在（返回 401 未读到有效 token），已收录为 `biz/fadada_richee`，需凭据
- [x] **fanruan-growth-advisor** 帆软增长谋士（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/fanruan_growth_advisor`
- [x] **fazhi-law** 同花顺法律AI助手（上游 auth_mode=token） —— 同上，`law_agent/mcp` 去掉 source 参数后直通，已探到 6 个工具（注入扫描 allow），收录为 `biz/fazhi_law`
- [x] **fbs-connector** 福帮手 —— 厂商自有端点，收录为 `biz/fbs_connector`
- [ ] **fenbi-baokao-decision** 报考决策 —— 阻塞：`market-api.fenbi.com` 上 `/mcp`、`/mcp/`、`/open/mcp`、`/.well-known/mcp`、`/.well-known/oauth-protected-resource` 全 404，**无通用入口，需向厂商申请** （2026-11-26 复查：各路径仍 404）
- [x] **finenter** 进门投研 —— 上游写 sse，实测 `/sse`→`/mcp` 端点存在（401，需凭据），已按 http 收录为 `data/finenter`
- [x] **flova** Flova（上游 auth_mode=oauth） —— 厂商自有端点，收录为 `creative/flova`
- [x] **fyopen-lawsearch** 法研·法律法规检索 —— 厂商自有端点，收录为 `biz/fyopen_lawsearch`
- [x] **gangtise-mcp** Gangtise投研（上游 auth_mode=token） —— 厂商自有端点，收录为 `data/gangtise_mcp`
- [x] **gaodun-job** 大学生实习就业助手 —— 厂商自有端点，收录为 `hr/gaodun_job`
- [x] **gildata** 恒生聚源 MCP（上游 auth_mode=token） —— 厂商自有端点，收录为 `data/gildata`
- [x] **gongyi-open-mcp** 腾讯公益机构服务平台 —— 厂商自有端点，收录为 `comm/gongyi_open_mcp`
- [x] **ima-mcp** ima知识库 —— 厂商自有端点，收录为 `office/ima_mcp`
- [x] **infimind-ecommerce-image** 极睿电商生图（上游 auth_mode=token） —— 厂商自有端点，收录为 `creative/infimind_ecommerce_image`
- [x] **infimind-video** 极睿视频（上游 auth_mode=token） —— 厂商自有端点，收录为 `creative/infimind_video`
- [x] **ioa** 零信任安全 iOA —— `tencent_ioa` pack，6 工具（端点取自官方 SDK）
- [x] **jiushuyun** 九数云BI —— 厂商自有端点，收录为 `biz/jiushuyun`
- [x] **kdocs** 金山文档 —— 实测端点匿名可连（去掉上游那两个标识调用方的头后仍返回完整 initialize），已探到 **258 个工具**（注入扫描 allow），收录为 `office/kdocs`；含 43 个删除类操作，清单里加了 notes 提醒
- [x] **kling-ai-plugin** 可灵 AI —— 厂商自有端点，收录为 `creative/kling_ai_plugin`
- [x] **kling-ai-plugin-ai** 可灵 AI —— 厂商自有端点，收录为 `creative/kling_ai_plugin_ai`
- [x] **kuaicha-search** 同花顺快查企业数据（上游 auth_mode=token） —— 上游 URL 带 `?source=<他方>`，去掉后通用入口实测直通，已探到 2 个工具（注入扫描 allow），收录为 `data/kuaicha_search`
- [x] **lexiang** 乐享知识库 —— 厂商自有端点，收录为 `comm/lexiang`
- [x] **lingxing-mcp** 领星ERP（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/lingxing_mcp`
- [x] **linkfox-product-selection** Linkfox 选品（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/linkfox_product_selection`
- [x] **mastergo-vibe-mcp** MasterGo —— 收录为上游条目 `mastergo`，官方双 runtime（magic-mcp 独立版 / vibe-mcp 桌面桥接）
- [x] **morningstar** 晨星 Morningstar —— 厂商自有端点，收录为 `data/morningstar`
- [x] **mx-ds-mcp** 东方财富妙想MCP —— 厂商自有端点，收录为 `data/mx_ds_mcp`
- [x] **mzl-trademark** 摩知轮商标查询 —— 厂商自有端点，收录为 `biz/mzl_trademark`
- [x] **neo-crm** 销售易CRM —— 厂商自有端点，收录为 `biz/neo_crm`
- [x] **opendata** 及刻智能·时空数据MCP（上游 auth_mode=token） —— 上游写 sse，实测 `/sse`→`/mcp` **直接连通**，已探到 6 个工具（注入扫描 allow），收录为 `data/opendata`
- [x] **pandadata** PandaData 金融数据 —— 厂商自有端点，收录为 `data/pandadata`
- [x] **picset-commerce-images** Picset AI 电商图片（上游 auth_mode=token） —— 厂商自有端点，收录为 `creative/picset_commerce_images`
- [x] **picset-video-generation** Picset AI 视频创作（上游 auth_mode=token） —— 厂商自有端点，收录为 `creative/picset_video_generation`
- [x] **pkulaw** 北大法宝·法律智能检索 —— 厂商自有端点，收录为 `biz/pkulaw`
- [x] **proboost** OpenBoost 跨境数据 —— 上游 sse 路径带 `/oauth/` 段；该托管平台约定是 `/mcp-servers/<名>/mcp`，去掉后实测直通，已探到 **84 个工具**（注入扫描 allow），收录为 `biz/proboost`
- [x] **qcc-legal** 企查查·法律数据 —— 厂商自有端点，收录为 `biz/qcc_legal`
- [x] **qixinhuiyan-mcp** 启信慧眼 —— 厂商自有端点，收录为 `data/qixinhuiyan_mcp`
- [x] **salesnail-instructor** SalesNail 讲师 —— 厂商自有端点，收录为 `biz/salesnail_instructor`
- [x] **salestouch** SalesTouch 经营执行 —— 厂商自有端点，收录为 `biz/salestouch`
- [x] **shanglv-mcp-gateway** 用友智能服务（AI BaaS） —— 厂商自有端点，收录为 `comm/shanglv_mcp_gateway`
- [x] **sq-company-dynamic** 上奇产业通-企业动态追踪（上游 auth_mode=token） —— 厂商自有端点，收录为 `data/sq_company_dynamic`
- [x] **tanyuan-assistant** TDC 文化智能体 —— 厂商自有端点，收录为 `biz/tanyuan_assistant`
- [x] **tdx-connector** 通达信 —— 实测 401 返回的是标准 MCP OAuth 受保护资源发现，按 `auth: oauth` 收录为 `data/tdx_connector`；装后 `totalclaw mcp login tdx_connector`
- [x] **teacher-assistant** 企鹅教师助手 —— 厂商自有端点，收录为 `hr/teacher_assistant`
- [x] **tec-do** Tec-Do 2.0 广告与增长情报 —— 厂商自有端点，收录为 `biz/tec_do`
- [ ] **tencent-health-nges** 腾讯健康NGES —— 阻塞：只有测试主机 `test.nges.qq.com`。生产写法 `nges.qq.com` 连不上（连接失败，非 DNS 问题，见下方说明） （2026-11-26 复查：`nges.qq.com` 直连与走代理均 TLS 握手失败，测试主机仍在）
- [x] **tencent-qidian-cs** 腾讯企点客服（上游 auth_mode=mcp） —— 厂商自有端点，收录为 `comm/tencent_qidian_cs`
- [x] **tencent-survey** 腾讯问卷 — 已实现 `tencent_survey`（问卷详情 + 游标翻页取答卷；上游为尊享版付费功能）
- [x] **tencent-tchouse-c** 腾讯云数据仓库 TCHouse-C —— `tencent_tchouse_c` pack，9 工具（端点取自官方 SDK）
- [x] **tencent-weiyun** 微云 —— 厂商自有端点，收录为 `office/tencent_weiyun`
- [x] **tongzhou-fin-research** 同舟金融研究 —— 厂商自有端点，收录为 `data/tongzhou_fin_research`
- [x] **tplus-api** 畅捷通T+ —— 厂商自有端点，收录为 `infra/tplus_api`
- [x] **weisheng-scrm** 微盛企微管家SCRM（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/weisheng_scrm`
- [x] **westock-mcp** 腾讯自选股 —— 厂商自有端点，收录为 `data/westock_mcp`
- [ ] **wind-finance** Wind 金融数据（上游 auth_mode=token） —— 阻塞：厂商按集成方单开路径（`vserver_<方名>`）。已查其 `.well-known/oauth-protected-resource`：resource 写的是主机根、授权服务器指向 `aifinmarket.wind.com.cn`，但根路径 301、`/mcp`、`/mcp/`、`/vserver/mcp/`、`/mcp-server/mcp` 全 404 —— **没有通用入口，必须向 Wind 申请自己的 vserver 路径** （2026-11-26 复查：根路径现为 nginx 默认页，各 mcp 路径仍 404）
- [ ] **wisenote** 百智WiseNote —— 阻塞：厂商 `.well-known/oauth-protected-resource` **把带他方产品名的那条路径声明为其规范资源**，连 OAuth 的 revocation_endpoint 也在同一段下；不存在不带该段的入口（`/mcp` 405、`/wisenote/meeting/mcp` 404）。虽然是标准 OAuth、凭据按用户各自授权，但把一条以别家产品命名的集成入口摆进我们的目录不合适 —— **需向厂商申请自己的入口** （2026-11-26 复查：资源元数据仍指向 `/workbuddy/wisenote/meeting/mcp`）
- [x] **wk-workbuddy** 威科先行 —— 厂商自有端点，收录为 `biz/wkinfo`
- [x] **xingtu-claw-risk** 天创信用星图MCP —— 上游写 sse，实测 `/mcp` 端点存在（401，需凭据），已按 http 收录为 `biz/xingtu_claw_risk`
- [x] **yingmi-mcp** 盈米MCP（上游 auth_mode=token） —— 厂商自有端点，收录为 `data/yingmi_mcp`
- [x] **youshu-bd-mate** 智客AI · 对公(To B)营销助手（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/youshu_bd_mate`
- [x] **yuandian-mcp** 华宇元典法律数据 —— 厂商自有端点，收录为 `biz/yuandian_mcp`
- [x] **yzf-invoice-mcp-server** 云帐房AI开票 —— 厂商自有端点，收录为 `data/yzf_invoice_mcp_server`
- [ ] **zfs-fssc-ai** 中兴新云AI智报（上游 auth_mode=token） —— 阻塞：只有演示主机 `mcpdemo.ztccloud.com.cn`（根路径 404，主机确实在）；`mcp.ztccloud.com.cn` 连不上。且上游传输是 sse （2026-11-26 复查：`mcp.ztccloud.com.cn` 仍 TLS 握手失败，演示主机仍 404）


#### C · 已核查受阻（8）

逐个查过官方文档，拿不到可验证的端点定义。**不猜端点、不写假 pack。**

- [x] **cnb-api** CNB —— 走 REST 那条路确实 401 受阻，但厂商发了官方 MCP `@cnbcool/mcp-server`（仓库在 cnb.cool，MIT）。已收录为 `dev/cnb`，需 API_TOKEN
- [x] **h3yun-connector** 氚云 — 已核查受阻：开放平台文档页报「系统加载错误」，需登录
- [x] **patsnap-search** 智慧芽专利&文献融合检索 — 已核查受阻：开放平台文档页 404，需登录开发者门户
- [x] **qingflow** 轻流 — 已核查受阻：Open API 需先在应用内安装扩展才能看文档与取 token
- [x] **sharecrm** 纷享销客CRM — 已核查受阻：纷享销客文档站是 SPA，抓不到端点定义
- [x] **tencent-docs** 腾讯文档 — 已核查受阻：v3 只给三元组请求头，文件管理端点在 v2，页面 404
- [x] **tencent-docs-oa** 腾讯文档企业版 — 已核查受阻：同 tencent-docs，且额外需 oneid-token
- [x] **xiaoe-cloud-cli** 小鹅通 — 已核查受阻：文档站只暴露目录，端点页需逐页登录

#### D · 上游是 CLI 封装而非 MCP（22）

WorkBuddy 里这些走的是 `cli.json`（命令行封装），不是 MCP 服务器。
若将来需要，可按其底层 REST API 单独实现，不必对齐上游形态。

- [x] **77ircloud** 铱云AI供应链 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **awesun** 向日葵远程控制 —— 上游走 CLI，但**厂商自己发了 MCP**（客户端自带 `awesun-mcp-server`，官方文档 service.oray.com/question/50091）。已收录为 `infra/awesun`，本机实探到 **30 个工具**（官方文档写 22，已过期），注入扫描 allow
- [x] **beisen-cli** 北森AI · HR专家 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **designkit-buddy-cli** 美图设计室 AI设计 CLI — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **emr-query** 弹性MapReduce — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **ihr-cli** i人事AI·HR专家 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **lemonclaw** 柠檬云 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **lovrabet-cli** Lovrabet CLI — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **mglc** 芒果灵创 CLI — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **miaoda** 秒哒应用搭建 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **seeyon-office-marketing-suite** 致远互联协同办公服务 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **shanlong-claw** 商龙经营洞察 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **tc-chengxin** 同程程心 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **tencentads** 腾讯营销投放 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **textin-xparse** TextIn xParse·智能文档解析 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **textin-xparse-ai** TextIn xParse·智能文档解析 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **tmeet** 腾讯会议 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **uupt** UU跑腿 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **woscli** 微盟 WOS CLI — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **wps-knowledgebase** WPS知识库 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **yunke-cli** 云客AI工作手机 — 上游是 CLI 封装而非 MCP，不在本仓范围
- [x] **zsxq** 知识星球 — 上游是 CLI 封装而非 MCP，不在本仓范围

#### E · 上游仅目录占位（1）

- [x] **ctrip-wendao** 携程问道 — 上游无 MCP 也无 CLI 配置，仅目录占位

### D2. 实现优先级建议

1. **先做凭据门槛低、通用性强的**：`tencent-survey` `jiandaoyun` `qingflow` `jinshuju`（表单类 API 简单且文档公开）
2. **再做企业刚需**：`tencent-docs` `kdocs` `tapd` `cnb-api` `tencent-weiyun` `baidu-netdisk`
3. **数据类按需**：`qcc-company` `tyc-mcp` `qixinhuiyan-mcp` 等需商业授权，先做 pack 骨架，凭据由客户自备
4. **`auth_mode: server-side` 的**（`kdocs` `jinshuju` `baidu-netdisk` `linear-mcp` `github` `tdx-connector`）
   上游由 WorkBuddy 服务端注入凭据，我们必须让用户自备 API Key，pack 里按标准 OAuth/Key 处理
5. **CLI 型连接器**（上游 26 个是 `cli.json` 而非 MCP）：这些在 WorkBuddy 里是命令行封装，
   我们要么实现为 REST pack，要么跳过 —— 逐个判断，不必强行对齐

### D2.5 已核查但受阻的连接器

这些查过官方文档但**拿不到可验证的接口契约**，不猜端点、不写假 pack：

- **cnb-api**（CNB）：`https://api.cnb.cool/openapi.json` 返回 401，规范需登录才能取
- **h3yun-connector**（氚云）：开放平台文档页报「系统加载错误」，需登录
- **xiaoe-cloud-cli**（小鹅通）：文档站只暴露目录结构，具体端点页需逐页登录查看
- **tencent-docs**（腾讯文档）：v3 只给了三元组请求头（Client-Id / Open-Id / Access-Token），
  具体文件管理端点在 v2 文档，页面 404
- **qingflow**（轻流）：Open API 需在应用内安装扩展后才能看到文档与 Access Token

拿到任一账号的开发者文档访问权后即可按 [PACKS.md](PACKS.md) 补 pack，引擎无需改动。

### D3. 已知差异与注意（说明性条目，非待办）

这三条是**记录**，不是要做的事 —— 写在这里是为了让后来者不必重新发现：

- 上游 7 个连接器用 SSE 传输，**agent 只实现了 stdio 与 streamable-HTTP**
  （`server_task.py` 没有 SSE 客户端，配置里的 `transport: sse` 是惰性字段）。
  我们自研的一律 stdio，不受影响。
- 上游 `timeout` 秒/毫秒混用（600 与 30000 并存）。自研统一用秒；
  从上游导入时 `> 3600` 一律按毫秒换算。
- 已删除两条被自研实现取代的外链条目：`biz/notion`、`dev/mcp_github`
  （后者上游 server 本身已归档）。
- **`tanyuan_assistant` 的 `/wb/mcp` 路径存疑，但按现有证据保留**（2026-08-23 复核）。
  它和被我否掉的 wisenote 长得像——都是「只有一条带前缀的路径能用」。区别在于证据强度：
  - wisenote 的路径段**是另一家产品的全名**，且厂商的 `oauth-protected-resource`
    把那条路径声明为规范资源 → 明确是给那家单开的，已否掉；
  - tanyuan 只有两个字母 `wb`，可以是任何缩写。实测 `/mcp`、`/mcp/`、`/open/mcp`、
    `/api/mcp`、`/tanyuan/mcp` 全是**没有 `WWW-Authenticate` 的裸 401**（边缘统一挡的），
    只有 `/wb/mcp` 回标准 MCP OAuth 质询，其 `resource` 也自指该路径。
  也就是说：既没有通用入口可换，也拿不到「wb 就是某产品」的实证。
  凭两个字母就删掉一个能用的条目，和凭两个字母就断定它没问题，都是瞎猜。
  **要定性得问厂商**；在那之前它按标准 OAuth 工作，用户各自授权，不影响使用。

---

## E 组 · 注册表读接口（`api/`，M1 已完成）

来源：「你做的这些 mcp，需要有一个分页查询的接口（支持多语言）；然后每一个 mcp
支持通过接口下来」。形状对齐 [`API.md`](API.md) ⓪，M2 平台服务接管时前端不用改。

- [x] **E1.1** `api/server/catalog.py`：就地读 `registry.json`（mtime 缓存，自动重载），
  筛选（`q`/`category`/`transport`/`launcher`/`tag`/`verified`/`no_credentials`）、
  排序、分页。**不落数据库**——注册表本来就是 Git 仓库，抄一份就得管同步，而同步会错。
- [x] **E1.2** 多语言：`lang=zh-CN|en`，不传按 `Accept-Language` 协商，认不出来回落
  `zh-CN`（语言标签写错不该让请求失败）。取值回落 **本语言 → 另一语言 → slug**；
  slug 排最后，`tencent_tchouse_c` 这种机器名不该抢在正经名字前面。
- [x] **E1.3** 全部 115 条补齐 `display_name_en`（90 条取自上游 `name_en`，25 条取厂商
  既有英文品牌名）。**没有就留空回落中文，不现译**——留空好过现译一个错的。
  字段已写进 [`SPEC.md`](../SPEC.md) 与 `scripts/gen_registry.py`。
- [x] **E1.4** 逐条目下载：`/files`（逐文件 sha256）、`/files/{path}`（单文件）、
  `/download`（tar.gz）。打包 mtime 与属主归零 → 同内容同字节 → ETag 稳定可缓存。
- [x] **E1.5** 路径穿越防线做在 `safe_join` **自身**（resolve 后判是否仍在条目目录内），
  不指望路由层或反向代理先规范化 `..`；软链外指一并挡掉。条目目录由已校验的
  `category`+`name` 拼出，不用 `entry['path']`（那是给客户端看的字符串）。
- [x] **E1.6** `api/tests` 39 个用例：穿越 7 例、分页边界 5 例、语言协商 9 例 + 回落、
  跨语言搜索、筛选、下载可复现与逐文件摘要一致、快照与磁盘逐字节相等。
  CI 新增 `api` job（`.github/workflows/ci.yml`）。
- [x] **E1.7** 两个被测试逮到的 bug：① 回落顺序里 slug 排在了另一种语言前面，
  只有英文名的条目在中文界面会显示 slug；② `{name:path}` 贪婪路由声明在前，
  把 `awesun/download` 整个吞成 name，下载与取文件两条路都进不来。

**刻意没做打包**：`catalog.py` 的 `REPO_ROOT` 指向 `api/` 的上一级，装成 wheel 挪到
别处就读不到条目数据。能装但装完读不到，比装不了更糟——所以只给 `api/requirements.txt`。

---

## F 组 · 追上游版本（2026-11-26 起）

明细与逐条清单见 [`upstream-updates-2026-11-26.md`](upstream-updates-2026-11-26.md)，
数据用 `scripts/check_upstream_updates.py` 重新生成。473 条 npx / uvx 条目中 122 条落后上游，本轮处理 106 条。

- [x] **F1** 官方参考服务器：PyPI 三条（fetch / git / time）升 2026.11.18，实测探测通过
- [x] **F1.1** `@modelcontextprotocol/*` npm 4 条已升 2.x（2026-11-27）：filesystem 2.4.0 / memory 2.2.1 / sequential-thinking 2.2.0 / everything 2.3.1
  - **不必等内置 Node 24**：2.x 的 engines 声明 node>=24，但实测 Node 22.22 下 initialize / list_tools / 典型工具调用（文件读写列目录、建实体读图、思考步骤、echo / 求和）全部正常，清单 `requires.node` 写 `>=22`；同样的调用在打包脚本下载的独立 Node 24.22.3 上也全过
  - 静态审核：许可证 / 出处两类告警经人工复核排除 —— npm 构建溯源证明显示 4 个包均由 modelcontextprotocol/servers 的 release.yml 在 tag v2.5.0（c799c855）构建，发布者 / 维护者 / 仓库与日期版一致；仓库 LICENSE 为 MIT→Apache-2.0 迁移中（见 review-2026-11-27-upstream-manual.json）
  - 顺带修 mcp_memory 两处旧问题：env 用了 agent 不支持的 `${VAR:-默认值}`、可选变量 default 被截成 `${HOME`；改为必填绝对路径（不给时 2.x 写进 npx 缓存，清缓存即丢）
  - 修 `review_static.py --apply`：种子条目没有 `verified` 字段时补上（以前判 warn 会替换落空，条目静默保持已审核）
  - 实探刷新 tools.json（16 / 9 / 1 / 16 个工具）；dep_gate --refresh 0 命中
  - agent 侧（已推送分支）：`fix/env-interpolation-defaults`（`3f21836bc` utils 支持 `${VAR:-默认值}` 与嵌套 —— 内置 filesystem / memory 预设以前设了变量也起不来；`121a353d5` sequential-thinking 预设钉 2.2.0）；`feat/mcp-render-requires-node`（`90422bdbf`，安装时核对 requires.node）
  - 更正此前判断：zerotoken 的原生扩展（sharp / node-pty / @napi-rs/canvas / clipboard / davey / @discordjs/opus）**全是 N-API**，跨 Node 版本二进制兼容，实测在 Node 24.22.3 下全部加载正常；内置 Node 升 24 的 qiye-app 改动（`prepare-vendor-cross.mjs` 默认 24.22.3）在本地分支 `chore/vendor-node-24`，属可选的对齐上游；另顺带发现当前钉的 22.22.3 已落后安全版 22.23.5
- [x] **F2** agent `mcp_presets.py` 的 mcp-server-time 同步（agent 工作区已改，未提交；合 main / bump submodule 待定）
- [x] **F3** `stripe` 改官方托管端点 `https://mcp.stripe.com`（OAuth），去掉密钥
- [x] **F4–F6** 101 条按「满 7 天的最新稳定版」升级，静态审核 + 旧版差分复核全部 allow
- [x] **F6.1** 冷却期 12 条复查（11-26 晚）：满 7 天的 2 条里 airtable_rashidazarang 4.0.1→5.1.0 已升；mailkite 维持 0.20.0 —— 上游 0.20.1/0.20.2 把依赖写成 `file:../node`，从 npm 装出来是悬空链接，启动即崩（dep_gate 告警发现，实装确认）
- [ ] **F6.2** 其余 10 条最早 11-30 才满 7 天，下一轮再升（清单见明细文末）。本会话设了每日定时复查（会话结束即失效）
- [x] **F7** 门禁：gen_registry --check --strict、scan-registry、dep_gate --refresh；chrome_devtools / playwright 重新探测
- [x] **F8** 老用户升级路径已查清：有「更新」按钮，但没有新版本提示（待办见明细 U3）
- [x] **F9** desktop_commander 安装期遥测：加 `npm_config_ignore_scripts=true`（运行时 env + `security.enforced_env`，老用户同步）。对照实测开关生效时 postinstall 不跑；依赖 ripgrep / sharp 已改用平台预编译包，全新缓存安装 + 探测 25 个工具正常
- [x] **F10** `review_static.py --apply` 以前会丢 `security.enforced_env`，已修：只换 scan_verdict / osv / reason，其余键原样保留并断言
- [x] **F11** **mcp 2.x 兼容（2026-11-26 发现）**：MCP Python SDK 2.0（7-28 发布）删了 v1 的 FastMCP、低层 `Server` 装饰器与 `McpError`，
  且 `mcp.server.fastmcp` 一导入就报错。153 条 uvx 条目里 50 条钉住的版本依赖 `mcp` 不设上界，全新安装会解析到 2.x；
  内存里扫代码确认 46 条用了被删的 API，启动即崩（hn 实测复现）。已统一前置 `--with mcp<2`（解析到 1.30.0，仍是 v1 API）。
  批量探测：免凭据的全部越过导入阶段；同时修出几处旧毛病：
  - mcp_sqlite / docker / dy_xhs 原先钉 `mcp==1.19.0`，1.19 用了 pydantic 私有函数 `eval_type_backport`，pydantic 2.14（10 月）删掉后也启动即崩 → 改钉 `mcp==1.30.0`，三条实测通过
  - timeserver：包提供的可执行名是 `mcp-timeserver`，与包名不同，uvx 找不到命令 → 改 `--from`，实测通过
  - 老用户：已装的参数不会自动变，需要点「更新」重装（同 U3）
- [x] **F12a** 修了 mcp 2.x 仍起不来的 5 条：另修 3 条，2 条经负责人确认下架（见 [removed-2026-11-26.md](removed-2026-11-26.md)）
  - [x] `alphavantage`：PyPI 包（最新 0.3.24，仅两个版本）启动时无条件从当前目录读 `pyproject.toml` 即崩 →
    改接 Alpha Vantage 官方托管端点 `https://mcp.alphavantage.co/mcp`（API Key 走 Bearer 头），用官方公开演示 key 实探 133 个工具，静态审核 allow
  - [x] `ds`：`from mcp.server import McpError` 只有 mcp 1.0–1.1.x 这样导出 → 钉 `--with mcp==1.1.3`（与包同期、无 pydantic 私有函数问题），实探 2 个工具
  - [x] `xiyan`：上游最新 0.1.7 入口指向不存在的函数 → 改 `python -m xiyan_mcp_server`；补未声明的 `--with pandas`；
    声明必填 `YML`（配置文件路径，说明里写明不要写 `mcp.transport`，否则传给 FastMCP 报错）。假配置实探 1 个工具
  - [x] `browser_use`（已下架）：没有真正的 stdio 模式 —— `--stdio` 是起 8000 端口 SSE 服务再拉外部 `mcp-proxy`（不在依赖里）；
    还写死 OpenAI gpt-4o（要 `OPENAI_API_KEY`）、要本机装 Playwright 浏览器；钉 browser-use==0.1.40 能过导入但仍起不来
  - [x] `database`（已下架）：依赖链 legion-query-runner **所有版本**硬依赖 `mysqlclient==2.1.1`，该包只有 Windows 预编译包，mac / Linux 需本机 MySQL 开发库现场编译，清单层面无解
- [x] **F12b** 9 条（alphavantage / x / adls2 / wolfram_alpha / home_assistant / tinybird / vikingdb / ancestry / adbpg）原先写 `requires_env: []`，装上即报缺变量退出 —— 已从包代码核出启动必需的变量补齐（含 `doc_url`），ancestry 的必填参数 `--gedcom-path` 用 `${ANCESTRY_GEDCOM_PATH}` 代入；adbpg 代码读 `ADBPG_DATABASE`（上游报错文案写成 ADBPG_NAME，以代码为准）。探测缺凭据时全部正确跳过，ancestry 填目录后实测 3 个工具。顺带：alphavantage 默认在 0.0.0.0:9464 起 Prometheus 指标服务，已用 `enforced_env` 关掉（`MCP_TELEMETRY_ENABLED=false`）
- [x] **F13** `scripts/probe_server.py` 以前整份 `yaml.safe_dump` 重写清单：缩进注释全丢、中部顶格注释被挪到文件头。已改成只局部替换 `tools:` 块与 `security` 的三个键，写回前断言解析结果与整体重写一致；全部 650 份清单离线回归（语义 / 注释 / 前缀不变 / 幂等）0 失败，desktop_commander 实探只变 probed_at
- [x] **F14（U3）** 桌面端「有新版本」提示 —— 已实现在两个仓库的功能分支 `feat/mcp-update-available`（本地提交，**未推送、未合并、未发版**）：
  - agent `06a04361d`：`list_installed()` 对注册表条目在有新版本时带 `update_available: {version}`（形状按本仓 API.md 的 InstalledEntry），
    `/v1/mcp/installed` 透传；纯数字点分比较、解析不了不提示；已下架不提示；注册表不可用 / 只有内置目录时不声称有新版本。MCP 相关 79 个用例通过
  - qiye-app `58268b7e0`：已安装页版本列显示「有新版本 x.y.z」、该行「更新」按钮突出；旧 agent 不带字段时不显示；补 en/ar/ms/vi 译文。McpMarketView 31 个用例通过
- [x] **F15** U3 发版（2026-11-27 完成：agent v0.68.53 = core-kernel `4c6da05f3`、main 合并 `b5300ca8a`；qiye-app 子模块指针 `b4b787dab`，check-agent-pointer 通过。另一会话在 core-kernel 补了措辞修复，随下次发版进 main）。原记录：（qiye-app 部分已合入 master：`58268b7e0` + F18 `99e8c6e42`，2026-11-27 用户确认后快进推送；agent 侧 feat/mcp-update-available、fix/url-safety-fake-ip-translated、fix/mcp-install-enabled-with-provided-env、fix/env-interpolation-defaults、feat/mcp-render-requires-node 等 totalclaw-agent-29 一轮落到 origin 后由本会话合进 core-kernel，再打版并 bump qiye-app 子模块）：agent 分支合进 core-kernel → main 并打版；qiye-app 分支合进 master 并 bump agent 子模块（`scripts/check-agent-pointer.mjs`）。
  合并前在共用的 agent 目录先看 `git diff HEAD -- totalclaw_core/mcp_hub.py totalclaw_qiye_api/mcp_hub_api.py`（另一会话会有并行改动）
- [x] **F16**（已随 v0.68.53 发版）agent `url_safety`：fake-ip 代理回 `::ffff:0:198.18.x.x` 式 AAAA 时整个域名被判私网 —— gitee raw 跳转主机被拦，
  桌面端 MCP 市场静默回落内置 26 条（开着 Clash 类 fake-ip 代理的用户都中）。修复在 agent 分支 `fix/url-safety-fake-ip-translated`（`79331c3e7`，
  含指纹重生成），修复前新用例失败、后通过；E2E 里注册表从 builtin 26 → remote 650。**已推送分支，待审阅合并**
- [x] **F17**（已随 v0.68.53 发版）agent `mcp_hub`：请求里带齐凭据安装仍被存成 `enabled: false`（render 只看 os.environ），桌面端每个带凭据的连接器装完都是停用。
  修复在 agent 分支 `fix/mcp-install-enabled-with-provided-env`（`762d22fc2`）；E2E 里 alphavantage / ancestry 装完即启用。**已推送分支，待审阅合并**
- [x] **F18** qiye-app 查毒代理 `mcpPackageGuard`：拉包体不带客户端 UA，Electron 默认浏览器 UA 被清华 PyPI 镜像 403（国内默认第一优先源）
  → 桌面端所有要现场下载的 uvx 连接器都装不上。修复在 qiye-app 分支 `fix/mcp-package-guard-artifact-ua`（`d57a3c938`），
  单测修复前失败、后通过（含真 npm / uv 装包），最小 Electron 脚本证实 net.fetch 带 uv UA 即 200。
  **已合入 qiye-app master（99e8c6e42）**；完整应用内已验证（2026-11-27）：空 uv 缓存、默认走清华镜像，修复后的构建 V3 13/13 通过；同条件下未修复的构建 uvx 连接器全部失败。（上次起不来 qiye-api 是 worktree 里 `resources/vendor` 是入库目录，`.venv` 没链接过去。）**已推送分支，待审阅合并**

## G 组 · 2026-11-27 全量杀毒查询

报告：[review-2026-11-27-full.md](review-2026-11-27-full.md)（623 条未下架条目逐个下载包体静态审核 + 依赖查毒 + 注册表文本查毒）。

- 结果：allow 464 / warn 153 / block 6；`--scan-registry` 0 命中；`dep_gate` 黑名单刷新后 0 命中。**未发现投毒或恶意代码。**
- warn 里的代码规则命中（下载即执行、外传端点、读浏览器凭据、预编译二进制、安装期脚本等）共 60 条，57 条有历次人工复核结论且本次命中与复核时一致；
  其余 3 条是作者弃用：bitcoin（bitcoin-mcp 全部版本被原维护者弃用）、mcp_brave_search、mcp_postgres（官方归档包，弃用说明写明「不再有安全保证」）。
- block 6 条，均非恶意：
  - didlogic：PyPI 上 4 个版本全部被作者撤回，理由「deleting」—— 作者在下线该包
  - flow_horustek、maxstat：端点 TLS 握手被断开（直连、走代理都一样），服务挂了或屏蔽本网络
  - morningstar：只有走本机代理时证书链自签（代理中间人）；直连 TLS 校验通过、返回标准 OAuth 质询 → 误报，维持现状
  - unreal_engine、xiaohongshu：端点是 localhost（用户本机自起的服务），「不是 HTTPS」不适用 → 维持现状
- [ ] **G1 待拍板下架**：didlogic、bitcoin、mcp_brave_search（注册表已有 brave_search 可替代）、mcp_postgres；flow_horustek、maxstat 先观察还是下架

## C2.2 · 免凭据但实探起不来的 108 条（2026-11-27 逐条重跑并留存 stderr 归因）

- 重试即通过 2：scrapling_fetch、webresearch（首次只是启动超时）
- 本机 npm 镜像（npmmirror）未同步、npm 官方源上存在 7：awwwards、castov、cloudgpu、octeract_context、open_apps、screenshotone、strava —— 清单没问题
- 实际要凭据、清单却没声明 ≈30：actors(APIFY_TOKEN)、agentql、agentset、airtable、dart、exchangerate、linear_tacticlaunch、lystbot、magic(API_KEY)、makehq、
  miro、naver_search、ns、posteverywhere、replicate、simple_openai_assistant、tiktok、voyp、zotero_kaliaboi、brightdata(API_TOKEN)、gmail_autoauth(OAuth 文件)、
  maigret(MAIGRET_REPORTS_DIR)、mongo(连接串)、nocodb、toolbox_sdk；浏览器 OAuth：finlight、palisadeemail、singlestore → 补 requires_env / auth
  - [x] 已补声明 27 条（变量名取自包报错原文或包源码），假凭据实探 21 条起得来并写回工具清单：actors、agentql、agentset（另需 AGENTSET_NAMESPACE_ID）、airtable、dart、linear_tacticlaunch、miro、ns、replicate、simple_openai_assistant、tiktok、voyp、zotero_kaliaboi、brightdata、kibela、naver_search、nocodb、maigret、exchangerate（包支持匿名免费档：运行时设 ALLOW_ANONYMOUS=true，key 改选填，开箱可用）、edinet（缺 `serve` 子命令）、minimax（见下）
  - 声明已对、但启动时就校验凭据 / 连库，假值起不来，等真凭据补探：magic、makehq（工具按账号场景动态生成）、posteverywhere（key 须 pe_live_ 开头）、mongo、toolbox_sdk
  - 未处理：lystbot（要先跑 `lystbot login`）、gmail_autoauth（要 GCP OAuth 密钥文件）、finlight / palisadeemail / singlestore（启动即拉浏览器 OAuth）
- [x] 顺带发现并修的清单错误（全注册表扫过同类）：
  - airtable：选填 MCP_TRANSPORT 默认值 `http`，桌面端会预填 → 服务器改起 HTTP、stdio 连不上；已去掉（连同只在 HTTP 模式用的 PORT）
  - minimax：MINIMAX_API_HOST 包里必填却标选填、默认值是一句说明文字；运行时 env 把 MINIMAX_API_RESOURCE_MODE 写死成说明文字（包静默改本地落盘）；MINIMAX_MCP_BASE_PATH 占位默认值 → 都已改。另：包启动时往 stdout 打一行纯文本，客户端记一条解析错误后照常工作（9 个工具），但关连接时报 BrokenResourceError，probe_server 因此写不了工具清单
  - **timeplus：运行时 env 写死了包 README 示例里作者自己的 Kafka 主机与账号（且关证书校验）**，每个用户的 Kafka 相关操作都会连到第三方主机 → 已去掉，改选填无默认。已装的老用户本地配置里仍有这串值，enforced_env 只能强制赋值、不能删除，需要 agent 侧支持「清单删除的 env 同步删掉」或在 MCP 医生里提示（待定）
- 启动命令写错（可执行名不对）6：cal、fidelis_memory、friday_memory、preloop、prometheus、zoom_search → 改 `--from 包 命令`
  - [x] 已修并实探写回工具清单 5 条：fidelis_memory（`--from … fidelis-mcp`，4 工具）、prometheus（`--from … prometheus-mcp-server` + 补必填 PROMETHEUS_URL，6 工具）、zoom_search（`zoom-search[mcp]` + `--with mcp<2`，1 工具）、python_interpreter / roundtable_ai（`--with mcp<2`，10 / 9 工具）
  - 未修：friday_memory（`friday` 可执行无输出，不是 MCP 入口）、preloop（只有 preloop-sync）、cal（npm 包 bin 缺 shebang，包本身坏）
- 缺子命令 / 必填参数 17：backlink_guard、forge、keystash、knowlyr_datacheck/modelaudit/sandbox、kordoc、kubernetes_containers、local_gpu_imagegen、minas_webdav、
  mobilebuildmcp、new_term_radar、omx_hyperliquid、phonedriver、serena_agent、xcodebuildmcp 等 → 从包文档查 MCP 启动子命令
  - [x] 已修并实探写回工具清单 13 条（入口取自包元数据 entry_points / npm bin 与源码）：
    - README 的 `# Claude Code` 注释被当成参数（全注册表仅此 4 条）：forge、phonedriver、octocrawl、omx_hyperliquid
    - MCP 服务器是另一个可执行：backlink_guard / new_term_radar / minas_webdav（`--from 包[mcp] *-mcp`）、kordoc（`npx -p kordoc kordoc-mcp`）
    - 缺 MCP 子命令：keystash `mcp`、local_gpu_imagegen `serve`、serena_agent `start-mcp-server`、mobilebuildmcp / xcodebuildmcp `mcp`
  - 包本身坏、清单层面修不了：knowlyr_datacheck / knowlyr_modelaudit / knowlyr_sandbox（用 mcp 1.x 低层装饰器，却按另一套签名调 `Server.run()`，mcp 1.x / 2.x 下都起不来）；friday_memory（没有 stdio MCP 入口）、preloop（MCP 只在其 HTTP API 服务里）、cal（npm bin 缺 shebang）→ 建议并入 G1 下架拍板
  - 本机前提：kubernetes_containers 要本机 kubeconfig 配有当前上下文，清单无误
- 依赖问题 7：python_interpreter、roundtable_ai（mcp 2.x，补 `--with mcp<2`）；chroma、davinci_resolve、markitdown、simple_pubmed、md_to_word_docx（缺依赖 / 版本冲突）
  - [x] 已修并实探写回工具清单 5 条：chroma（包钉死 mcp 1.6.0，前置 `--with pydantic<2.10`）、simple_pubmed（`--with mcp<2 --with pydantic-settings` + 必填 PUBMED_EMAIL）、md_to_word_docx（`[mcp]` extra）、markitdown（显式钉预发布依赖 azure-ai-contentunderstanding==1.2.0b1，不整体放开 --prerelease）、ns_private_access（必填 NETSKOPE_BASE_URL / NETSKOPE_API_TOKEN）
  - [x] 平台 / 运行时声明：eda_agent `platforms: [win32]`（导入即用 ctypes.WINFUNCTYPE）、sidehand `platforms: [win32, linux]`（npm os 字段）、confluent `requires.node: '>=22.23.4'`
  - 本机前提：davinci_resolve 要本机装 DaVinci Resolve
- 其余 ~30 条 stderr 没有明确原因（静默退出、需本机 bun / IDE / 平台限制等），逐条看
- [ ] 修完逐条重探；凭据类并入 credentials-needed.md

