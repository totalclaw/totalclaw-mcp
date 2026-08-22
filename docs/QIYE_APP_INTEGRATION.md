# totalclaw-qiye-app 侧改造清单（M2）

## 1. 现状

- `renderer/components/qiye-api/McpServerPanel.vue` → IPC `QIYE_API_MCP_*` → `/v1/mcp/servers`：**真正写 agent 配置**，但只有 preset/自定义两种表单，无市场、无状态、无工具列表。
- `views/PluginsView.vue` + `packages/mcp-market`：Electron 内存态 `McpMarket`，`start()` 自己 spawn `npx`，**与 agent 完全无关，不落盘**。
- 两者都在 feature `mcp-market` 门控下。

## 2. 目标形态

```
/mcp  McpMarketView.vue
├── Tab「市场」      GET /v1/mcp/registry           搜索框 · 分类 chips · verified 徽标 · 工具数 · 安装按钮
│     └── McpInstallDialog.vue
│           step1 选择运行时（runtime_candidates，灰掉 available=false 并显示 reason）
│           step2 requires_env 表单（复用 plugin requires_env 渲染器；secret → password）
│           step3 plan 预览：渲染后的配置块（脱敏）· 工具列表 · 安全结论 · 是否覆盖
│           step4 install → 轮询 /v1/mcp/jobs/{id}，逐行显示 log，完成显示 state/tools
└── Tab「已安装」    GET /v1/mcp/installed          状态卡：ready ✅ / connecting ⏳ / failed ❌ / disabled ⏸ / needs_setup ⚠️ / update_available ⬆️
      操作：启用/禁用（既有 enable）· 更新 · 卸载 · 重新探测 · OAuth 登录（url+auth=oauth）· 查看工具
      顶部：「重载 MCP」 POST /v1/mcp/reload
```

`McpServerPanel.vue` 保留为「高级：手动添加」折叠区；`PluginsView.vue` 的 MCP 段删除，`packages/mcp-market` 仅保留类型导出或整体移除。

## 3. IPC 通道（`packages/ipc-contracts/src/index.ts`）

```ts
QIYE_API_MCP_REGISTRY        = 'qiyeApi:mcp:registry'        // GET /v1/mcp/registry
QIYE_API_MCP_REGISTRY_INFO   = 'qiyeApi:mcp:registryInfo'    // GET /v1/mcp/registry/{id}
QIYE_API_MCP_PLAN            = 'qiyeApi:mcp:plan'            // POST /v1/mcp/plan
QIYE_API_MCP_INSTALL         = 'qiyeApi:mcp:install'         // POST /v1/mcp/install   rateLimit 10
QIYE_API_MCP_JOB             = 'qiyeApi:mcp:job'             // GET /v1/mcp/jobs/{id}
QIYE_API_MCP_INSTALLED       = 'qiyeApi:mcp:installed'       // GET /v1/mcp/installed
QIYE_API_MCP_UPDATE          = 'qiyeApi:mcp:update'          // POST /v1/mcp/servers/{n}/update
QIYE_API_MCP_RELOAD          = 'qiyeApi:mcp:reload'          // POST /v1/mcp/reload   rateLimit 6
QIYE_API_MCP_STATUS          = 'qiyeApi:mcp:status'          // GET /v1/mcp/status
```

`main/ipc/qiyeApi.ipc.ts` 中一律使用 `postRaw / getRaw`（与既有 `QIYE_API_MCP_UPSERT` 同理：camel→snake 会把 `GITHUB_TOKEN` 折成 `github_token`）。`env` 对象原样透传。

## 4. 版本门控与配额

- feature id：`mcp-market`（沿用）；`personal-single` / `offline` 关闭。
- 配额：`version-feature-matrix.md §F` 建议「专业 5 / 旗舰不限」。在 `QIYE_API_MCP_INSTALL` 处理器里读 `GET /v1/mcp/installed` 计数，超限返回 `{ code: 'QUOTA_EXCEEDED', limit }`，UI 引导升级。
- 离线版：`/v1/mcp/registry` 会返回 `source: "builtin"`（presets 回退），UI 显示「离线目录」提示。

## 5. 多账号 / 企业

- 无需任何 tenant 参数：每个登录账号已有独立 `TOTALCLAW_HOME`（`accountScope.ts`），qiye-api 子进程随账号切换重启。
- 企业私有注册表：登录态 user 带 `org` 时，IPC 把 `org` 与平台 JWT（`auth-service` 的 accessToken）作为 `bearer_token` 传给 `/v1/mcp/registry?org=` 与 `/v1/mcp/install`；agent 侧再带到平台 API。
- 托管运行时（M3）：`TOTALCLAW_MCP_ORG` 由 `qiyeApiProc.ts` 的 `extraEnv` 注入，安装器自动优先 `hosted`。

## 6. 文案（i18n key 建议）

```
mcp.market.title            MCP 市场
mcp.market.installed        已安装
mcp.install.runtime         运行方式
mcp.install.env             凭据与环境变量
mcp.install.preview         安装预览
mcp.install.progress        正在安装
mcp.state.ready             已连接
mcp.state.connecting        连接中
mcp.state.failed            连接失败
mcp.state.disabled          已禁用
mcp.state.needs_setup       待配置
mcp.state.update_available  有更新
mcp.reload                  重载 MCP
mcp.reload.note             重载会使提示缓存失效，下一条消息将重新发送完整上下文
```
