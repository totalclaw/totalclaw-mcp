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

- [x] **C1** 包版本全部 pin 到实测最新稳定版，`--strict` 已零警告，CI 已切 `--strict`
  - 顺带修出两个继承自 agent presets 的真 bug：
    `@modelcontextprotocol/server-sequentialthinking` 少了连字符（npm 上不存在）；
    `@modelcontextprotocol/server-time` 在 npm 上根本没有，该服务器是 PyPI 的
    `mcp-server-time`，runtime 已从 npx 改为 uvx —— 正是 agent `RETIRED_LAUNCH_SPECS`
    要防的「包不存在 → 挂到超时」那类问题
- [ ] **C2** `scripts/probe_server.py`：沙箱启动 → `list_tools` → 生成 `tools.json` + `security` 块（注入扫描 10 模式 + 出网域名）；先手动跑 dev/web 两类
- [ ] **C3** Ed25519 签名：移植 `totalclaw-plugins/scripts/sign_registry.sh` → 产出 `registry.json.sig`
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
- [ ] **D0.9** CI：`totalclaw-mcp-server --check` + `pytest` + `gen_registry.py --check`
- [ ] **D0.10** 发布 `totalclaw-mcp-servers` 到 PyPI（registry 的 `uvx` runtime 依赖它）

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

#### B · 待实现，需先取得可验证的接口契约（75）

拿到任一家的开发者文档或沙箱账号后，照 [PACKS.md](PACKS.md) 写 pack 即可，引擎无需改动。
优先级参考 D2。

- [ ] **ai-hive** AI-HIVE
- [ ] **archive-hospital-mcp** 腾讯健康全周期管理平台
- [ ] **bazhuayu** 八爪鱼
- [ ] **bugly-token** Bugly 质量概览（上游 auth_mode=token）
- [ ] **camscanner-mcp** 扫描全能王
- [ ] **chuhaijiang** 出海匠
- [ ] **cisp-mcp** 水滴征信（上游 auth_mode=token）
- [ ] **dcs-cloud** DCS Cloud（上游 auth_mode=token）
- [ ] **dknowc-mcp** 深知可信工作台
- [ ] **duoguan-fengchao** 夺冠蜂巢（上游 auth_mode=token）
- [x] **edgeone-pages** EdgeOne Makers — 已实现 `tencent_edgeone`（站点/域名/刷新预热）
- [ ] **ezjoin-meeting** EzyJoin智慧会议
- [ ] **fadada-richee** 法大大睿契
- [ ] **fanruan-growth-advisor** 帆软增长谋士（上游 auth_mode=token）
- [ ] **fazhi-law** 同花顺法律AI助手（上游 auth_mode=token）
- [ ] **fbs-connector** 福帮手
- [ ] **fenbi-baokao-decision** 报考决策
- [ ] **finenter** 进门投研
- [ ] **flova** Flova（上游 auth_mode=oauth）
- [ ] **fyopen-lawsearch** 法研·法律法规检索
- [ ] **gangtise-mcp** Gangtise投研（上游 auth_mode=token）
- [ ] **gaodun-job** 大学生实习就业助手
- [ ] **gildata** 恒生聚源 MCP（上游 auth_mode=token）
- [ ] **gongyi-open-mcp** 腾讯公益机构服务平台
- [ ] **ima-mcp** ima知识库
- [ ] **infimind-ecommerce-image** 极睿电商生图（上游 auth_mode=token）
- [ ] **infimind-video** 极睿视频（上游 auth_mode=token）
- [ ] **ioa** 零信任安全 iOA
- [ ] **jiushuyun** 九数云BI
- [ ] **kdocs** 金山文档（上游 auth_mode=server-side）
- [ ] **kling-ai-plugin** 可灵 AI
- [ ] **kling-ai-plugin-ai** 可灵 AI
- [ ] **kuaicha-search** 同花顺快查企业数据（上游 auth_mode=token）
- [ ] **lexiang** 乐享知识库
- [ ] **lingxing-mcp** 领星ERP（上游 auth_mode=token）
- [ ] **linkfox-product-selection** Linkfox 选品（上游 auth_mode=token）
- [ ] **mastergo-vibe-mcp** MasterGo 莫高设计
- [ ] **morningstar** 晨星 Morningstar
- [ ] **mx-ds-mcp** 东方财富妙想MCP
- [ ] **mzl-trademark** 摩知轮商标查询
- [ ] **neo-crm** 销售易CRM
- [ ] **opendata** 及刻智能·时空数据MCP（上游 auth_mode=token）
- [ ] **pandadata** PandaData 金融数据
- [ ] **picset-commerce-images** Picset AI 电商图片（上游 auth_mode=token）
- [ ] **picset-video-generation** Picset AI 视频创作（上游 auth_mode=token）
- [ ] **pkulaw** 北大法宝·法律智能检索
- [ ] **proboost** OpenBoost 跨境数据
- [ ] **qcc-legal** 企查查·法律数据
- [ ] **qixinhuiyan-mcp** 启信慧眼
- [ ] **salesnail-instructor** SalesNail 讲师
- [ ] **salestouch** SalesTouch 经营执行
- [ ] **shanglv-mcp-gateway** 用友智能服务（AI BaaS）
- [ ] **sq-company-dynamic** 上奇产业通-企业动态追踪（上游 auth_mode=token）
- [ ] **tanyuan-assistant** TDC 文化智能体
- [ ] **tdx-connector** 通达信（上游 auth_mode=server-side）
- [ ] **teacher-assistant** 企鹅教师助手
- [ ] **tec-do** Tec-Do 2.0 广告与增长情报
- [ ] **tencent-health-nges** 腾讯健康NGES
- [ ] **tencent-qidian-cs** 腾讯企点客服（上游 auth_mode=mcp）
- [ ] **tencent-survey** 腾讯问卷
- [ ] **tencent-tchouse-c** 腾讯云数据仓库 TCHouse-C
- [ ] **tencent-weiyun** 微云
- [ ] **tongzhou-fin-research** 同舟金融研究
- [ ] **tplus-api** 畅捷通T+
- [ ] **weisheng-scrm** 微盛企微管家SCRM（上游 auth_mode=token）
- [ ] **westock-mcp** 腾讯自选股
- [ ] **wind-finance** Wind 金融数据（上游 auth_mode=token）
- [ ] **wisenote** 百智WiseNote
- [ ] **wk-workbuddy** 威科先行
- [ ] **xingtu-claw-risk** 天创信用星图MCP
- [ ] **yingmi-mcp** 盈米MCP（上游 auth_mode=token）
- [ ] **youshu-bd-mate** 智客AI · 对公(To B)营销助手（上游 auth_mode=token）
- [ ] **yuandian-mcp** 华宇元典法律数据
- [ ] **yzf-invoice-mcp-server** 云帐房AI开票
- [ ] **zfs-fssc-ai** 中兴新云AI智报（上游 auth_mode=token）

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

### D3. 已知差异与注意

- [ ] **D3.1** 上游 7 个连接器用 SSE 传输，**agent 只实现了 stdio 与 streamable-HTTP**；我们自研的一律 stdio，不受影响
- [ ] **D3.2** 上游 `timeout` 秒/毫秒混用（600 与 30000 并存），自研统一用秒
- [ ] **D3.3** 已删除两条被自研实现取代的外链条目：`biz/notion`、`dev/mcp_github`（上游该 server 已归档）
