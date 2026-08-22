# totalclaw-mcp

TotalClaw MCP 平台 —— MCP 服务器的注册中心、分发与托管网关。

- **totalclaw-agent** 用命令安装：`totalclaw mcp install github --env GITHUB_PERSONAL_ACCESS_TOKEN=… --yes`
- **totalclaw-qiye-app** 用接口安装：`POST /v1/mcp/install {"spec":"github"}` → 轮询作业 → 已安装状态卡
- 安装完成即热加载，下一轮对话可直接调用 `mcp__github__*` 工具

阅读顺序：[ARCHITECTURE.md](ARCHITECTURE.md) → [SPEC.md](SPEC.md) → [docs/API.md](docs/API.md) → [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) → [docs/QIYE_APP_INTEGRATION.md](docs/QIYE_APP_INTEGRATION.md)

> **要开始对接？直接读 [docs/TODO.md](docs/TODO.md)** —— agent 侧（A 组）、qiye-app 侧（B 组）、注册表数据（C 组）的可勾选任务清单与端到端验收项，每项都指回上面对应的细节文档。

## 仓库结构

```
registry/servers/<category>/<name>/mcp.yaml   清单（单一事实源）
registry.json                                  索引（scripts/gen_registry.py 生成）
scripts/gen_registry.py                        生成 / --check 校验索引
scripts/import_presets.py                      从 totalclaw-agent 的 mcp_presets / mcp_catalog 导入种子
scripts/probe_server.py                        CI：沙箱探测工具快照 + 安全扫描（M2）
api/        NestJS 平台服务（M2）
gateway/    托管 MCP 网关（M3）
web/        SSR 市场站（M4）
```

## 快速开始（维护者）

```bash
python3 scripts/import_presets.py --agent ../totalclaw-agent     # 首次：导入 27 条种子
python3 scripts/gen_registry.py                                   # 生成 registry.json
python3 scripts/gen_registry.py --check                           # CI：索引与磁盘一致性
```

## 贡献一个 MCP 服务器

1. 复制 `registry/_TEMPLATE/mcp.yaml` 到 `registry/servers/<category>/<name>/mcp.yaml`，按 `SPEC.md` 填写。
2. 包版本必须精确 pin；秘密放 `requires_env`，不要写进 `args`。
3. `python3 scripts/gen_registry.py` 通过后提 PR；维护者审核后置 `verified`。
