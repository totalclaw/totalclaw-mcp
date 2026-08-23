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
- [ ] **C2.1（剩余）** 41 个条目实测返回 401 —— 端点在、说 streamable-HTTP，
  只差各家凭据。拿到任一家凭据后 `export <VAR>=... && python3 scripts/probe_server.py <名>`
  即可补齐其 `tools.json` 与 `security` 块。
- [x] **C3** Ed25519 签名脚本 `scripts/sign_registry.py`（`--keygen` / `--sign` / `--verify`）
  - 已实测完整链路：生成密钥 → 签名 → 验签通过 → 篡改一个字段后验签**正确失败** → 恢复后再通过
  - 私钥只从 `MCP_REGISTRY_SIGNING_KEY` 或库外文件读，keygen 默认写到 `~/.totalclaw-mcp-keys`
    并置 600；`.gitignore` 已挡 `*.ed25519.key`
  - 为什么需要签名：`files[].sha256` 只保证「下载到的文件没被中途改」，
    但分发点整体被替换时索引和文件会被一起换掉；签名把信任根挪到私钥上
- [ ] **C3.1** 生成正式密钥对、把私钥放进 CI secret、提交 `registry.pub`、
  在 CI 的 registry job 末尾加 `--sign` 并提交 `.sig`
  （本次未提交 `.sig` / `registry.pub`：那是一次性测试密钥签的，
  提交上去会造成「已官方签名」的假象）
- [x] **C4.1** 推送 Gitee 仓库 `jlzdyx/totalclaw-mcp`（分支 **master**，与 `registry.json` 的 `raw_base` 路径一致）
- [ ] **C4.2** 分发通道的可见性方案 —— **决策推迟到对接时**（当前仓库为私有）
  - 已实测（2026-08-22）：
    - 匿名 `raw/master/registry.json` → **403**（对照 totalclaw-plugins/tools 均为 302，它们是公开仓）
    - 匿名 Gitee API v5 contents → **404**
    - **认证 sparse clone → 可用**：`git clone --depth 1 --filter=blob:none --sparse` + 凭据可正常拉取私有仓文件。agent 侧 `plugin_hub._download_sparse` 走的正是这条路，**私有分发有现成通道**
    - 整仓体积：`registry.json` gzip 后 10 KB，`registry.json + registry/` 打包 22 KB → 单个签名 bundle 分发完全可行，无需逐文件取数
  - 对接时二选一：
    - **(a) 转公开**：Gitee → 管理 → 仓库设置 → 开源；`mcp_hub` 直接匿名拉 raw，无需改动
    - **(b) 保持私有**：客户端**不得**携带 Gitee token（个人令牌是账号级的，且桌面端可被提取）。走平台中转：`api/` 服务端持 token 同步私有仓 → 对外发签名 bundle，客户端用自身已有身份（qiye-app 的平台 JWT / agent 的 license）鉴权。此方案把 `api/` 从 M2 提前到 M1
- [x] **C4.3** CI（`.github/workflows/ci.yml`）：
  - `gen_registry.py --check --strict`（版本未 pin 直接失败）
  - `totalclaw-mcp-server --check` + `pytest`
  - 生成物一致性：跑完 `gen_manifests.py --force` 与 `gen_registry.py` 后必须无 diff，
    防止改了 servers/ 却忘了重新生成清单
- [x] **C5（英文描述部分）** pack 规范加 `description_en`，21 条自研条目全部补齐；
  `gen_manifests` 改为 `description` 取英文、`description_zh` 取中文 —— 此前两处都填中文，
  英文界面上就只能看到中文
- [ ] **C5.1** 图标 `icon.svg`：需要设计资源，不自造

---

## 验收（端到端场景，全过即对接完成）

> 已脚本化：`python3 scripts/acceptance.py`（每项独立临时 `TOTALCLAW_HOME`，不碰真实配置，
> 可随时重跑）。手工点一遍的问题是下次改动后没人会再点。
> 最近一次：**通过 6 · 失败 0 · 需人工 1**。

- [x] **V1** CLI 装上并在 `installed` 可见（本环境探测失败→按设计置 disabled，退出码 3 也算通过）
- [x] **V2** 缺 env 退出码 2 + `missing_env` 列表正确
- [ ] **V3**（需人工）qiye-app 界面全流程要在 Electron 里点。其依赖的 REST 契约已由
  agent 仓 `test_mcp_hub_api.py` 11 个用例覆盖；界面本身不假装脚本能验
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

#### B · 厂商自有 MCP 端点（62 已收录 / 8 阻塞）

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
  只剩 zfs-fssc-ai，它本就是演示主机（同域 `mcp.ztccloud.com.cn` DNS 解析不了）。
  「上游写 sse」不等于「只有 sse」，值得先探一下再判死；探的时候路径也别照抄整段。
- **平台身份鉴权（2）** —— `auth_mode: server-side`，凭据由那个平台自己注入，我们拿不到。
- **非生产主机（1）** —— `test.nges.qq.com`，测试环境不进目录。已试过同域生产写法
  `nges.qq.com/mcp`，DNS 解析不了。

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
- [ ] **fenbi-baokao-decision** 报考决策 —— 阻塞：他方专属路由（https://market-api.fenbi.com/workbuddy/mcp —— 需自行向厂商申请独立路由）
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
- [ ] **kdocs** 金山文档（上游 auth_mode=server-side） —— 阻塞：平台身份鉴权（auth_mode=server-side，凭据由上游平台注入，我们拿不到）
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
- [ ] **tdx-connector** 通达信（上游 auth_mode=server-side） —— 阻塞：平台身份鉴权（auth_mode=server-side，凭据由上游平台注入，我们拿不到）
- [x] **teacher-assistant** 企鹅教师助手 —— 厂商自有端点，收录为 `hr/teacher_assistant`
- [x] **tec-do** Tec-Do 2.0 广告与增长情报 —— 厂商自有端点，收录为 `biz/tec_do`
- [ ] **tencent-health-nges** 腾讯健康NGES —— 阻塞：非生产主机（test.nges.qq.com）
- [x] **tencent-qidian-cs** 腾讯企点客服（上游 auth_mode=mcp） —— 厂商自有端点，收录为 `comm/tencent_qidian_cs`
- [x] **tencent-survey** 腾讯问卷 — 已实现 `tencent_survey`（问卷详情 + 游标翻页取答卷；上游为尊享版付费功能）
- [x] **tencent-tchouse-c** 腾讯云数据仓库 TCHouse-C —— `tencent_tchouse_c` pack，9 工具（端点取自官方 SDK）
- [x] **tencent-weiyun** 微云 —— 厂商自有端点，收录为 `office/tencent_weiyun`
- [x] **tongzhou-fin-research** 同舟金融研究 —— 厂商自有端点，收录为 `data/tongzhou_fin_research`
- [x] **tplus-api** 畅捷通T+ —— 厂商自有端点，收录为 `infra/tplus_api`
- [x] **weisheng-scrm** 微盛企微管家SCRM（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/weisheng_scrm`
- [x] **westock-mcp** 腾讯自选股 —— 厂商自有端点，收录为 `data/westock_mcp`
- [ ] **wind-finance** Wind 金融数据（上游 auth_mode=token） —— 阻塞：他方专属路由（https://mcp.wind.com.cn/vserver_workbuddy/mcp/ —— 需自行向厂商申请独立路由）
- [ ] **wisenote** 百智WiseNote —— 阻塞：他方专属路由（https://100wiser.com/workbuddy/wisenote/meeting/mcp —— 需自行向厂商申请独立路由）
- [x] **wk-workbuddy** 威科先行 —— 厂商自有端点，收录为 `biz/wkinfo`
- [x] **xingtu-claw-risk** 天创信用星图MCP —— 上游写 sse，实测 `/mcp` 端点存在（401，需凭据），已按 http 收录为 `biz/xingtu_claw_risk`
- [x] **yingmi-mcp** 盈米MCP（上游 auth_mode=token） —— 厂商自有端点，收录为 `data/yingmi_mcp`
- [x] **youshu-bd-mate** 智客AI · 对公(To B)营销助手（上游 auth_mode=token） —— 厂商自有端点，收录为 `biz/youshu_bd_mate`
- [x] **yuandian-mcp** 华宇元典法律数据 —— 厂商自有端点，收录为 `biz/yuandian_mcp`
- [x] **yzf-invoice-mcp-server** 云帐房AI开票 —— 厂商自有端点，收录为 `data/yzf_invoice_mcp_server`
- [ ] **zfs-fssc-ai** 中兴新云AI智报（上游 auth_mode=token） —— 阻塞：传输不支持（type=sse；agent 只支持 stdio 与 streamable-HTTP）


#### C · 已核查受阻（8）

逐个查过官方文档，拿不到可验证的端点定义。**不猜端点、不写假 pack。**

- [x] **cnb-api** CNB — 已核查受阻：OpenAPI 端点返回 401，规范需登录
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
- [x] **awesun** 向日葵远程控制 — 上游是 CLI 封装而非 MCP，不在本仓范围
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
