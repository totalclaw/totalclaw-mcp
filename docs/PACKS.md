# Pack 规范 —— 声明式定义一个 MCP 连接器

一个 pack = 一个连接器 = 一个 MCP 服务器。文件放在
`servers/totalclaw_mcp_servers/packs/<name>.yaml`，**文件名必须等于 `name`**。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✅ | `^[a-z][a-z0-9_]*$`，等于文件名，也是 agent 里的 `mcp_servers.<name>` 键 |
| `display_name` | ✅ | 展示名（中文优先） |
| `description` | ✅ | 一句话说清能做什么 |
| `base_url` | ✅ | API 根地址。非回环地址必须 `https://` |
| `auth` | | 鉴权（none/header/bearer/query/basic/token_exchange/signature/tencent_cloud），见下 |
| `defaults` | | `{timeout: 30, headers: {...}}` |
| `response` | | 业务错误码检查，见下 |
| `tools` | ✅ | 至少 1 个 |
| `optional_env` | | 可选环境变量名列表 |
| `docs` | | 上游 API 文档链接 |

## `auth` — 八种鉴权

凭据**只能**来自环境变量，pack 里写死密钥会被校验拒绝。

```yaml
auth: {type: bearer, env: GITHUB_TOKEN}                    # Authorization: Bearer <值>
auth: {type: header, name: X-Api-Key, env: ACME_KEY}       # 自定义 header
auth: {type: query,  name: key, env: TENCENT_MAP_KEY}      # 密钥放 query
auth: {type: basic,  env: PWD_VAR, env_user: USER_VAR}     # HTTP Basic
auth: {type: none}                                          # 公开 API
```

### `token_exchange` — 先换令牌再调接口

企业微信、飞书、钉钉不接受直接用 secret 调业务接口，必须先换 `access_token`。
引擎负责换取并在进程内缓存到过期前 60 秒（上游对换取接口有频次限制）。

```yaml
auth:
  type: token_exchange
  token_url: https://qyapi.weixin.qq.com/cgi-bin/gettoken
  token_method: GET                  # GET | POST
  token_query: {corpid: ${WECOM_CORP_ID}, corpsecret: ${WECOM_SECRET}}
  # token_body: {...}                # POST 时用 body（飞书是这种）
  token_pick: access_token           # 从响应里取令牌的点号路径
  expires_pick: expires_in           # 有效期秒数，可选
  place: query                       # 令牌放哪：query | header
  name: access_token                 # query 参数名 / header 名
  prefix: ""                         # header 前缀，如 "Bearer "
  requires_env: [WECOM_CORP_ID, WECOM_SECRET]   # 必填，用于缺凭据时提前报错
```

### `signature` — 签名鉴权

一整类国内 API 不直接传密钥，而是要求 `MD5(AppKey + 时间戳 + SecretKey)` 这样的一次性签名
（企查查是典型）。引擎负责按规则算并注入。

```yaml
auth:
  type: signature
  algorithm: md5                 # md5 | sha1 | sha256 | hmac_sha256
  parts: ["${QCC_APP_KEY}", "{timestamp}", "${QCC_SECRET_KEY}"]
  uppercase: true                # 签名结果转大写
  # hmac_key: ${SECRET}          # algorithm=hmac_sha256 时的密钥
  inject:
    headers: {Token: "{signature}", Timespan: "{timestamp}"}
    query: {key: ${QCC_APP_KEY}}
  requires_env: [QCC_APP_KEY, QCC_SECRET_KEY]
```

可用占位符：`${ENV}` 环境变量、`{timestamp}` 秒级时间戳、`{timestamp_ms}` 毫秒、
`{nonce}` 随机串、`{signature}` 算出的签名（只能出现在 `inject` 里）。

### `tencent_cloud` — 腾讯云 TC3-HMAC-SHA256

腾讯云所有云 API（CloudBase / EdgeOne / Bugly / TCHouse / 营销投放 / SMS / OCR …）
共用这套四步签名。引擎已实现，pack 里只需声明服务名与版本。

```yaml
auth:
  type: tencent_cloud
  service: tcb                     # 云产品的 service 名
  version: "2018-06-08"            # 该产品的 API 版本
  secret_id_env: TENCENTCLOUD_SECRET_ID
  secret_key_env: TENCENTCLOUD_SECRET_KEY
  region_env: TENCENTCLOUD_REGION  # 可选，优先于下面的 region
  region: ap-shanghai
```

云 API 形状固定：**`method: POST`、`path: /`，动作放在 `tools[].headers` 的 `X-TC-Action`**，
入参是 JSON body。失败时是 HTTP 200 + `Response.Error`，所以配套写：

```yaml
response:
  error_field: Response.Error.Code
  ok_value: "__never__"
  message_field: Response.Error.Message
```

## `response` — 业务错误码

**这是国内 API 接入最容易踩的坑**：失败时返回 `HTTP 200 + errcode != 0`，
只看 HTTP 状态码会把失败当成功喂给模型。

```yaml
response:
  error_field: errcode      # 点号路径
  ok_value: 0               # 该值表示成功
  message_field: errmsg     # 失败原因字段
```

响应里没有该字段时不判为失败（有些接口成功时不返回 errcode）。

## `tools[]` — 每个工具

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✅ | `^[a-z][a-z0-9_]*$`，pack 内唯一。最终工具名是 `mcp__<pack>__<name>` |
| `description` | ✅ | 给模型看的。写清**做什么、返回什么、有无副作用** |
| `method` | | `GET`（默认）/ `POST` / `PUT` / `PATCH` / `DELETE` |
| `path` | ✅ | 相对 `base_url`，可含 `{param}` |
| `params` | | JSON Schema，描述工具入参 |
| `query` / `body` / `headers` | | 请求要素，值里可用占位符 |
| `read_only` | | 默认 `GET` 为 true。**写操作必须显式 `false`** —— agent 据此走审批 |
| `pick` | | 只回传响应里的这个点号路径，如 `data.items` |
| `max_items` | | 数组结果最多回传多少条 |
| `max_chars` | | 序列化后最大字符数，默认 16000 |
| `timeout` | | 覆盖默认超时 |

### 占位符

| 写法 | 含义 |
|---|---|
| `{param}` | 工具入参。**整串就是一个占位符时保留原始类型**（`"{limit}"` → 数字 5，不是 `"5"`） |
| `${auth}` | 鉴权凭据本身（少数 API 要把 key 拼进 URL） |
| `${ENV_VAR}` | 任意环境变量 |

缺失的可选参数会让所在的 query 项 / body 字段**整条丢弃**，而不是发空串——
空串对多数 API 意味着「显式传空」，语义不同。路径里的占位符缺值则直接报错，
绝不生成 `/repos//issues` 这种畸形路径。

## 写描述的要求

工具描述是模型唯一的判断依据，写不好模型就选错工具。

- 说清**返回什么**：「返回企业名与统一社会信用代码」比「查询企业」有用。
- 说清**副作用**：写操作要明说，如「这会真实推送消息给企业成员」。
- 参数描述带上**取值范围与格式**：`"每页条数，1-100，默认 20"`、`"纬度,经度"`。
- 枚举用 `enum`，模型会照着填。

## 检查清单

```bash
totalclaw-mcp-server --check <name>      # 定义合法性
totalclaw-mcp-server <name> --describe   # 确认工具与凭据
cd servers && python -m pytest tests -q  # 全量回归
```

新增 pack 后，跑 `scripts/gen_manifests.py --force` 与 `scripts/gen_registry.py`
把它接进 registry，agent 才能 `totalclaw mcp install <name>`。
