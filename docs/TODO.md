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
- [ ] **A1.1** 新建 `totalclaw_core/mcp_hub.py`（对标 `tool_hub.py`）：`fetch_registry / search / resolve / plan / install / update / remove / list_installed / check_updates / reload`
  - 注册表 URL：env `TOTALCLAW_MCP_REGISTRY`，默认 `https://gitee.com/jlzdyx/totalclaw-mcp/raw/master/registry.json`
  - 缓存：`$TOTALCLAW_HOME/mcp/registry-cache.json`，TTL `TOTALCLAW_MCP_REGISTRY_TTL`（默认 3600s）
  - 离线回退：注册表不可达且无缓存 → 用 `mcp_presets.PRESETS` 生成伪条目（`source: builtin`）
  - 复用（import，不复制）：`plugin_hub._download_raw / _download_sparse / _verify_files / _signature_gate / is_hub_entry`
- [ ] **A1.2** 新建 `totalclaw_core/mcp_hub_render.py`：`mcp.yaml` → `mcp_servers.<name>` 渲染
  - runtime 选择顺序：显式 `--runtime` > `TOTALCLAW_MCP_ORG` 已设且清单含 `hosted` > `http` > 第一个 `shutil.which(launcher)` 可用的 `stdio`（docker 额外 `docker info`）
  - env 键：默认 `MCP_<NAME_UPPER>_<VAR>`；清单声明 `env_key` 则保留原变量名（27 条种子全部用 `env_key`，零迁移）
  - `auth: header` → `Authorization: Bearer ${MCP_<NAME>_API_KEY}`（与 `mcp_admin._provision_bearer` 同构）
  - 渲染结果必须能通过 `mcp_admin._normalize_server_spec`（写单测保证，见 A6.1）
- [ ] **A1.3** 新建 `totalclaw_core/mcp_hub_lock.py`（对标 `skills_hub_cache_body.HubLockFile`）：
  - `$TOTALCLAW_HOME/mcp/installed.json`：`{name: {id, version, runtime, source, bundle_sha256, installed_at, updated_at}}`
  - `$TOTALCLAW_HOME/mcp/audit.log`：`<ISO8601Z> <action> <name> <source> <verdict>`
- [ ] **A1.4** `install()` 九步流水线（resolve → gate → download/verify → validate/render → security → write → probe → reload → finalize），每步 `on_log` 回调
  - security 步：`mcp_security.validate_mcp_server_entry` + `package_pin_problem` + `osv_check`
  - write 步：秘密 `save_env_value` → `.env`；`mcp_admin.add_server`；`tools.json` 预填 `mcp/schema-cache/<name>.json`
  - probe 步：复用 `_mcp_config_impl._probe_single_server`；失败 → `set_enabled(False)` + `needs_setup`
  - reload 步：进程内有 MCP loop → `reload_mcp_servers()`；否则交给 `cli.py` 5s 配置监视
  - 门禁：未 `verified` 需 `allow_unverified` 且默认 `enabled=False`；`scan_verdict: block` 永不安装、`ask` 需确认
- [ ] **A1.5** `remove()` 同时清理：`mcp_admin.remove_server` + `installed.json` 条目 + `mcp/schema-cache/<name>.json` + `mcp-tokens/<name>*.json` + `.env` 中 `MCP_<NAME>_*` 键

### A2. CLI 子命令
- [ ] **A2.1** 新建 `totalclaw_cli/_mcp_hub_impl.py`，挂到既有 `mcp` 子命令树（`_main_impl.py` 的 mcp parser）：
  `search / info / plan / install / update / uninstall / installed / status / reload`
  - 全部支持 `--json`（JSON 到 stdout，日志到 stderr）
  - 退出码：`0` 成功 / `1` 错误 / `2` 缺必填 env（`--json` 含 `missing_env[]`）/ `3` 探测失败已保存为 disabled
  - `install` 旗标：`--env K=V ... --runtime ID --yes --no-probe --disabled --allow-unverified --overwrite --json`
- [ ] **A2.2** `mcp catalog` 改为 `mcp search` 的别名；`mcp presets` 保留为离线回退入口（数据源仍是 `mcp_presets`）
- [ ] **A2.3** shell 补全与 `/help`：`_profiles_impl.py` 补全表、`_commands_impl.py` CommandDef 补新子命令

### A3. qiye_api 接口
- [ ] **A3.1** 新建 `totalclaw_qiye_api/mcp_hub_api.py`（对标 `skill_shop_api.py`，`build_router()` + `register` 进 `server.py:1454` 的 GA 路由表）：
  - `GET /v1/mcp/registry`（代理+缓存，响应含 `source: remote|cache|builtin`）
  - `GET /v1/mcp/registry/{id}`、`POST /v1/mcp/plan`
  - `POST /v1/mcp/install` → **202** `{job_id, poll_url}`；409 同名作业进行中；422 `{detail:"missing_env", missing_env:[]}`
  - `GET /v1/mcp/jobs`、`GET /v1/mcp/jobs/{job_id}?tail=200`（job 结构见 API.md §②）
  - `GET /v1/mcp/installed`（installed.json + `get_mcp_status()` 合并）
  - `POST /v1/mcp/servers/{name}/update`（202）、`POST /v1/mcp/reload`、`GET /v1/mcp/status`
- [ ] **A3.2** `_notify_mcp_change()`：安装/卸载/更新作业末尾执行 `reload_mcp_servers()` + 对热池 agent `refresh_tools()`（对标 `skill_shop_api._notify_skill_change`）
- [ ] **A3.3** 既有 `DELETE /v1/mcp/servers/{name}` 扩展为调用 A1.5 的完整清理（保持响应形状兼容）
- [ ] **A3.4** 契约文档：更新 agent 仓 `docs/integration/MCP_SERVER_MANAGEMENT.md`（新增端点 + 「热加载已由作业完成」说明）

### A4. 既有 bug 顺手修（清单与行号见 AGENT_INTEGRATION.md §5）
- [ ] **A4.1** `_mcp_config_impl.py` 各 `cmd_mcp_*` 失败返回非零退出码；`catalog --install` 返回值透传
- [ ] **A4.2** `_dump_impl.py` MCP 计数改读 `mcp_servers`（当前恒为 0）
- [ ] **A4.3** `is_mcp_tool_parallel_safe` 改用 `mcp_naming` 解析（当前旧前缀判断，`supports_parallel_tool_calls` 失效）
- [ ] **A4.4** `prompt_builder_body.py` 两处 playwright 工具名改双下划线 `mcp__playwright__*`
- [ ] **A4.5** `website/docs` 两篇 MCP 文档的工具命名更新为 `mcp__<server>__<tool>`
- [ ] **A4.6** 统一 `mcp add --preset` 命名空间（当前只认 `codex`，与 `mcp presets` 两套目录）

### A5. 环境变量与文档
- [ ] **A5.1** 注册 env：`TOTALCLAW_MCP_REGISTRY / TOTALCLAW_MCP_API_BASE / TOTALCLAW_MCP_REGISTRY_TTL / TOTALCLAW_MCP_REQUIRE_SIGNATURE / TOTALCLAW_MCP_TELEMETRY / TOTALCLAW_MCP_ORG`，补进 `website/docs/reference/environment-variables.md`
- [ ] **A5.2** `totalclaw doctor` MCP 段增加：installed.json 与 config 的一致性、update_available 提示

### A6. 测试
- [ ] **A6.1** `test_mcp_hub_render.py`：本仓 27 条种子逐条渲染 → 必须通过 `_normalize_server_spec`；`env_key` 保留断言；runtime 选择矩阵
- [ ] **A6.2** `test_mcp_hub_install.py`：本地假注册表（http.server）端到端；sha256 篡改必须失败；未 verified 需 `--allow-unverified`；卸载清理完整性
- [ ] **A6.3** `test_mcp_hub_api.py`：202 + 轮询、409、422 missing_env、reload 响应形状
- [ ] **A6.4** CLI 退出码矩阵（0/1/2/3）

---

## B 组 · totalclaw-qiye-app 改造（M2，依赖 A1–A3）

### B1. IPC 层
- [ ] **B1.1** `packages/ipc-contracts/src/index.ts` 新增 9 个通道：
  `QIYE_API_MCP_REGISTRY / REGISTRY_INFO / PLAN / INSTALL / JOB / INSTALLED / UPDATE / RELOAD / STATUS`
- [ ] **B1.2** `main/ipc/qiyeApi.ipc.ts` 实现 handler：**一律 `postRaw / getRaw`**（camel→snake 会把 `GITHUB_TOKEN` 折成 `github_token`，参照既有 `QIYE_API_MCP_UPSERT` 的注释）；限流 install=10 / reload=6
- [ ] **B1.3** `preload/index.ts` 暴露 `window.electronAPI.qiyeApi.mcp*`
- [ ] **B1.4** 配额门控：INSTALL handler 里按版本矩阵（专业 5 / 旗舰不限）计数，超限返回 `{code:'QUOTA_EXCEEDED', limit}`

### B2. 统一市场页
- [ ] **B2.1** 新建 `renderer/views/McpMarketView.vue`：Tab「市场」（registry 搜索 + 分类 chips + verified 徽标 + 工具数）/ Tab「已安装」（状态卡 ready/connecting/failed/disabled/needs_setup/update_available；操作：启停/更新/卸载/重新探测/OAuth 登录；顶部「重载 MCP」按钮）
- [ ] **B2.2** 新建 `renderer/components/mcp/McpInstallDialog.vue` 四步向导：
  选 runtime（灰掉 `available=false` 并显示 reason）→ `requires_env` 表单（复用 plugin requires_env 渲染器，`secret` 密码框）→ `plan` 预览（脱敏配置块/工具列表/安全结论/覆盖提示）→ install + 轮询 job 逐行日志；422 `missing_env` 回到表单
- [ ] **B2.3** 路由 `/mcp` + 侧边栏入口；feature id 沿用 `mcp-market`
- [ ] **B2.4** `McpServerPanel.vue` 降级为「高级：手动添加」折叠区（保留既有 preset/custom 能力）
- [ ] **B2.5** 删除 `PluginsView.vue` 的 MCP 段与 `packages/mcp-market` 内存注册表（或仅留类型导出）；清理 `feature-handlers.ts` 的 `MCP_LIST/INSTALL/UNINSTALL/START/STOP` 通道
- [ ] **B2.6** i18n 文案（key 建议见 QIYE_APP_INTEGRATION.md §6）

### B3. 企业与多账号
- [ ] **B3.1** 多账号验证：切换账号（不同 `TOTALCLAW_HOME`）后市场/已安装状态各自独立
- [ ] **B3.2** （M3 联动）登录态含 org 时：`/v1/mcp/registry?org=` 透传 + `bearer_token` 传平台 JWT；`qiyeApiProc.ts` `extraEnv` 注入 `TOTALCLAW_MCP_ORG`

---

## C 组 · 本仓注册表数据（与 A 并行）

- [ ] **C1** 消掉 18 条「包未 pin 版本」警告：逐条查上游最新稳定版并写死（`gen_registry.py --strict` 通过后，把 CI 切到 `--strict`）
- [ ] **C2** `scripts/probe_server.py`：沙箱启动 → `list_tools` → 生成 `tools.json` + `security` 块（注入扫描 10 模式 + 出网域名）；先手动跑 dev/web 两类
- [ ] **C3** Ed25519 签名：移植 `totalclaw-plugins/scripts/sign_registry.sh` → 产出 `registry.json.sig`
- [ ] **C4** 推送 Gitee 仓库 `jlzdyx/totalclaw-mcp` + CI（`gen_registry.py --check`）
- [ ] **C5** 为高频条目补 `description` 英文与 `icon.svg`（mcp_github 为参考范例）

---

## 验收（端到端场景，全过即对接完成）

- [ ] **V1** CLI：`totalclaw mcp install mcp_time --yes --json` → exit 0；`totalclaw mcp installed --json` 可见；新会话中模型能调 `mcp__mcp_time__*`
- [ ] **V2** CLI 缺 env：`totalclaw mcp install mcp_github --yes --json` → exit 2 + `missing_env:["GITHUB_PERSONAL_ACCESS_TOKEN"]`
- [ ] **V3** qiye-app：市场搜索 → 安装向导填 env → job 日志逐步显示 → 已安装卡片 `ready` + 工具数正确，全程无重启
- [ ] **V4** 篡改注册表条目 sha256 → 安装失败于 verify 阶段，config.yaml 无残留
- [ ] **V5** 卸载后：config.yaml / .env / installed.json / schema-cache 全部干净
- [ ] **V6** 断网：`/v1/mcp/registry` 返回 `source:"builtin"`，presets 仍可安装
- [ ] **V7** 双账号互不可见对方安装的 MCP
