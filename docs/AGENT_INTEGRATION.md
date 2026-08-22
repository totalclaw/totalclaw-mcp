# totalclaw-agent 侧改造清单（M1）

目标：新增一个 `mcp_hub` 安装器，使 `totalclaw mcp install <spec>` 与 `POST /v1/mcp/install` 都能从注册表安装并热加载。全部复用既有基础设施，不新增运行时。

## 1. 新文件

| 文件 | 对标 | 职责 |
|---|---|---|
| `totalclaw_core/mcp_hub.py` | `totalclaw_core/tool_hub.py` | 注册表拉取/缓存、spec 解析、`plan()`、`install()`、`update()`、`remove()`、`list_installed()`、`check_updates()` |
| `totalclaw_core/mcp_hub_render.py` | `totalclaw_cli/mcp_catalog.CatalogEntry.server_config` | `mcp.yaml` → `mcp_servers.<name>` 渲染 + `.env` 键映射 + runtime 选择 |
| `totalclaw_core/mcp_hub_lock.py` | `skills_hub_cache_body.HubLockFile` | `$TOTALCLAW_HOME/mcp/installed.json` + `audit.log` |
| `totalclaw_cli/_mcp_hub_impl.py` | `totalclaw_cli/_skills_hub_impl.py` | `search/info/plan/install/update/uninstall/installed/status/reload` 子命令，`--json`，非零退出码 |
| `totalclaw_qiye_api/mcp_hub_api.py` | `totalclaw_qiye_api/skill_shop_api.py` | `/v1/mcp/registry|plan|install|jobs|installed|status|reload`，202 作业 + 轮询 |

## 2. 直接复用（只 import，不复制）

```python
from totalclaw_core.plugin_hub import (
    _download_raw, _download_sparse, _verify_files, _signature_gate, is_hub_entry,
)                                                   # tool_hub.py 就是这样做的
from totalclaw_core.mcp_admin import add_server, remove_server, set_enabled, list_servers, McpAdminError
from totalclaw_core.tools.mcp_security import validate_mcp_server_entry
from totalclaw_core.tools.osv_check import check_package_for_malware
from totalclaw_cli.mcp_catalog import package_pin_problem          # 抽到公共处或直接引用
from totalclaw_cli._mcp_config_impl import _probe_single_server     # 连接 + list_tools 探测
from totalclaw_core.tools.mcp_tool import reload_mcp_servers, get_mcp_status
from totalclaw_core.tools.mcp_tool.schema_cache import write_cache  # 预填 schema-cache
from totalclaw_cli._config_impl import save_env_value               # 秘密落 .env
from totalclaw_core.tools.mcp_presets import PRESETS                # 离线回退 + 名字对齐
```

## 3. `install()` 状态机

```
resolve ──▶ gate(verified/scan_verdict) ──▶ download ──▶ verify(sha256+sig)
   │                                                          │
   ▼                                                          ▼
 400 spec                                              validate_manifest(SPEC §4)
                                                              │
                                                              ▼
                                                    render(runtime, env) ──▶ missing_env? ──▶ exit 2 / 422
                                                              │
                                                              ▼
                                 validate_mcp_server_entry + package_pin_problem + osv_check
                                                              │
                                                              ▼
                               save_env_value(MCP_<NAME>_<VAR>) ──▶ mcp_admin.add_server(enabled=?)
                                                              │
                                                              ▼
                                                   schema-cache 预填(tools.json)
                                                              │
                                   ┌──────────── probe? ──────┴──────────────┐
                                   ▼ ok                                      ▼ fail
                        reload_mcp_servers()                   set_enabled(False) + needs_setup → exit 3
                                   │
                                   ▼
                          installed.json + audit.log + 遥测
```

## 4. 关键实现细节

- **runtime 选择**：`--runtime` > `TOTALCLAW_MCP_ORG` 已设且清单含 `hosted` > `http` > 第一个 `shutil.which(launcher)` 成功的 `stdio`。`docker` 还需 `docker info` 可用。
- **`.env` 键**：`MCP_<NAME_UPPER>_<VAR>`，`NAME_UPPER = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()`；http `auth: header` 沿用 `mcp_admin` 的 `MCP_<NAME>_API_KEY`。
- **覆盖策略**：同名已存在且 `installed.json` 无记录（用户手写或 preset）→ 需 `--overwrite`；有记录且版本不同 → 走 `update`。
- **热加载**：进程内有 MCP loop（qiye_api、TUI 网关、gateway）→ 直接 `reload_mcp_servers()`；纯 CLI 进程 → 依赖 `cli.py` 的 5s 配置监视（已存在）。qiye_api 里额外对热池 agent 调 `refresh_tools()`（对照 `skill_shop_api._notify_skill_change`）。
- **离线**：注册表不可达且无缓存 → 回退 `mcp_presets.PRESETS` 生成伪条目（`source: builtin`，`verified: true`，无 files → 跳过下载/校验，直接 `add_preset`）。
- **探测**：复用 `_probe_single_server(name, cfg, timeout=cfg.connect_timeout)`，它已做 `.env` 加载 + `${VAR}` 插值 + ExceptionGroup 拆包。
- **遥测**：`POST {TOTALCLAW_MCP_API_BASE}/mcp/servers/{id}/events`，3s 超时，失败静默。

## 5. 顺手修复（调研中发现的既有 bug）

| 位置 | 问题 | 修复 |
|---|---|---|
| `totalclaw_cli/_mcp_config_impl.py` 各 `cmd_mcp_*` | 失败 `return` 不设退出码 | 返回 int 并由 `mcp_command` 透传 `sys.exit` |
| `_mcp_config_impl.py:825-832` | `catalog --install` 返回值被丢弃 | 透传 |
| `totalclaw_cli/_dump_impl.py:76-79` | 读 `config["mcp"]["servers"]`，计数恒 0 | 改读 `mcp_servers` |
| `mcp_tool/__init__.py:313-322 is_mcp_tool_parallel_safe` | 仍按 `mcp_` 单下划线解析，`supports_parallel_tool_calls` 失效 | 用 `mcp_naming.split_mcp_tool_name` |
| `agent/prompt_builder_body.py:917-922, 973-978` | 浏览器策略提示里工具名是旧格式 `mcp_playwright_*` | 改 `mcp__playwright__*` |
| `website/docs/.../mcp.md`、`mcp-config-reference.md` | 工具命名文档过期 | 更新为双下划线 |
| `_mcp_config_impl.py:34-42` `_MCP_PRESETS` | `mcp add --preset` 只认 `codex`，与 `mcp presets` 两套命名空间 | 统一指向注册表 / `mcp_presets` |

## 6. 测试要点

- `tests/totalclaw_core/test_mcp_hub_render.py`：每个种子清单渲染结果必须通过 `mcp_admin._normalize_server_spec`。
- `tests/totalclaw_core/test_mcp_hub_install.py`：假注册表（本地 http 服务器）→ 安装 → `config.yaml` 断言 → `.env` 断言 → `installed.json` 断言；sha256 篡改必须失败；未 verified 必须需要 `--allow-unverified`。
- `tests/totalclaw_qiye_api/test_mcp_hub_api.py`：202 + 轮询 + `missing_env` 422。
- CLI 退出码矩阵测试。
