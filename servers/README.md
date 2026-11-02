# servers/ — TotalClaw 自研 MCP 服务器

这里是**我们自己实现的 MCP 服务器**。agent 与 qiye-app 安装的是本目录的代码，
不依赖任何第三方托管端点。

```bash
pip install -e servers                    # 本包没发到 PyPI，别用 uvx totalclaw-mcp-servers（名字可被抢注）

totalclaw-mcp-server --list               # 列出全部服务器
totalclaw-mcp-server --check              # 校验全部定义（CI 用，不发请求）
totalclaw-mcp-server github --describe    # 打印工具与所需凭据
totalclaw-mcp-server github               # 以 stdio 运行，供 MCP 客户端连接
```

## 两类实现

| 类型 | 位置 | 适用 | 新增成本 |
|---|---|---|---|
| **声明式 pack** | `totalclaw_mcp_servers/packs/<name>.yaml` | REST API + 凭据 → N 个工具（绝大多数连接器） | 写一份 YAML，零代码 |
| **原生服务器** | `totalclaw_mcp_servers/native/<name>.py` | 有状态协议 / 复杂解码（IMAP、浏览器、本地应用） | 写 Python |

之所以做成声明式，是因为上百个连接器的共性就是「带密钥调 REST API」。
一份引擎 + N 份 YAML，比 N 份互相复制的样板代码好维护得多。

## 引擎做了什么

`totalclaw_mcp_servers/engine/`

| 模块 | 职责 |
|---|---|
| `spec.py` | pack 规范与校验：凭据只能来自环境变量、非回环必须 https、工具名唯一、`defaults` 仅限 agent 支持的键 |
| `render.py` | 模板渲染。整串占位符保留原始类型（`per_page` 是数字不是 `"5"`）；缺失的可选参数整项丢弃而非发空串；路径参数缺失直接报错并做 URL 编码 |
| `client.py` | 发请求、注入鉴权、**业务错误码检查**、响应裁剪、凭据脱敏 |
| `token_exchange.py` | 企业微信/飞书/钉钉这类「先换 access_token」的鉴权，带进程内过期缓存 |
| `server.py` / `native_server.py` | 装配成 MCP 低层 Server（stdio），工具带 `readOnlyHint` 注解 |

三个容易被忽略、但直接决定可用性的点：

1. **业务错误码**。企业微信/钉钉/飞书失败时返回的是 `HTTP 200 + errcode!=0`。只看状态码会把失败当成功喂给模型。pack 里用 `response.error_field` 声明，引擎负责判定。
2. **凭据不落配置**。pack 只写环境变量名，真值在 `$TOTALCLAW_HOME/.env`。错误信息里的密钥会被脱敏。
3. **错误是返回值不是异常**。处理器永不抛裸异常，一律返回 `{"success": false, "error": "<人话>"}`，模型看到的是可读原因而非堆栈。

## 写一个新连接器

见 [../docs/PACKS.md](../docs/PACKS.md)。最小形态：

```yaml
name: acme
display_name: Acme
description: 查询 Acme 工单。
base_url: https://api.acme.com
auth: {type: bearer, env: ACME_TOKEN}
tools:
  - name: list_tickets
    description: 列出工单，按更新时间倒序。
    method: GET
    path: /v1/tickets
    query: {status: "{status}", limit: "{limit}"}
    pick: data
    max_items: 30
    params:
      type: object
      properties:
        status: {type: string, enum: [open, closed], description: 工单状态}
        limit: {type: integer, description: "返回条数，1-100"}
```

然后：

```bash
totalclaw-mcp-server --check acme          # 校验
python3 ../scripts/gen_manifests.py --force  # 生成 registry 清单
python3 ../scripts/gen_registry.py           # 更新 registry.json
```

## 测试

```bash
cd servers && python -m pytest tests -q     # 31 个用例，不发真实网络请求
```
