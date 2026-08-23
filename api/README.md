# api/ — 注册表读接口

两部分：**上半是已实现的 Python 读接口**（就地读仓库，M1 就能用）；下半是 M2 平台服务
（NestJS + Mongo）的设计，接口形状与上半一致，接管时前端不用改。

---

## 一、已实现：`api/server`（FastAPI，只读，无数据库）

数据源就是**仓库本身**——`registry.json` 加 `registry/servers/**`。注册表本来就是一个
Git 仓库，读接口没必要再往数据库里抄一份：抄了就得管同步，而同步是会错的。
`registry.json` 的 mtime 变了会自动重载，不用重启。

```bash
pip install -r api/requirements.txt
python3 -m uvicorn api.server.app:app --port 3101 --reload    # 必须在仓库根目录跑
```

Swagger 在 `/api/docs`。

> 为什么不打包成 wheel：`catalog.py` 的 `REPO_ROOT` 指向 `api/` 的上一级，装到别处
> 就读不到条目数据。能装但装完读不到，比装不了更糟。

### 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | `{ok, servers}` |
| GET | `/registry.json` | 完整索引快照，与磁盘逐字节一致 |
| GET | `/api/mcp/servers` | **分页查询**，见下 |
| GET | `/api/mcp/categories` | `[{category, label, count}]`，label 随语言 |
| GET | `/api/mcp/servers/{name}` | 详情：索引字段 + `manifest`（mcp.yaml 全文）+ `tools_detail` + `readme_md` |
| GET | `/api/mcp/servers/{name}/files` | 逐文件 `{path, sha256, size}` + `bundle_sha256` |
| GET | `/api/mcp/servers/{name}/files/{path}` | 取单个文件原文 |
| GET | `/api/mcp/servers/{name}/download` | 整条目 `tar.gz` |

`{name}` 收短名（`awesun`）或完整 id（`totalclaw-mcp/infra/awesun`）；`/files` 与
`/download` 只认短名（`name` 全库唯一，SPEC §1 有保证）。

### 分页查询

```
GET /api/mcp/servers?q=&category=&transport=stdio|http&launcher=npx|uvx|docker
                    &tag=&verified=&no_credentials=&page=1&page_size=24&lang=zh-CN
→ { items: [Entry & {display_name_localized, description_localized, category_label, lang}],
    total, page, page_size, total_pages, lang }
```

- `page_size` 上限 100，超了返回 422（不静默截断）。
- **页码越界夹到最后一页**，不返回空列表——返回空的话前端只看到「没有条目」，
  会以为目录空了。
- `q` 同时搜中英文名、中英文描述、标签和工具名：用户输入的语言和界面语言是两回事，
  中文界面搜 `github` 也得搜得到。
- `no_credentials=true` 只看 `requires_env` 为空的，即装完不用填凭据就能跑的。

### 多语言

`lang=zh-CN|en`；不传就按 `Accept-Language` 协商（`zh-CN,zh;q=0.9,en;q=0.8` 取第一段），
认不出来的一律回落 `zh-CN`——语言标签写错不该让请求失败。

取值回落顺序：**本语言 → 另一语言 → slug**。slug 排最后是因为它是
`tencent_tchouse_c` 这种机器名，比另一种语言的正经名字难读得多。目录里一个没有
名字的条目毫无用处，所以宁可回落也不留空。

英文名来自清单的 `display_name_en`（115 条已补齐），用的是厂商**既有的**英文品牌名；
没有就留空回落中文，不现译（SPEC §字段）。

### 下载与校验

`tar.gz` 打包时把 mtime 与属主归零，同样的内容打出同样的字节，所以 `ETag` 稳定、能走
缓存。响应头同时给两个摘要，别搞混：

- `X-Archive-Sha256` —— 这个压缩包字节的 sha256；
- `X-Bundle-Sha256` —— 索引里的 `bundle_sha256`，是**文件清单**的摘要，不是压缩包的。
  客户端要按 `/files` 逐条校验，别拿它去比 tar.gz。

包内统一一层同名目录（`awesun/mcp.yaml`），解开时不会把文件散到当前目录。

### 安全

`{path}` 是外部输入，`safe_join` 在**函数自身**做防线（resolve 后判是否仍在条目目录内），
不指望路由层或反向代理先帮忙规范化 `..`；软链指到目录外也挡掉（resolve 会跟过去）。
条目目录由已校验的 `category` + `name` 拼出，不用 `entry['path']`——那是给客户端看的
字符串，不该拿来拼本地路径。

### 测试

```bash
python3 -m pytest api/tests -q        # 在仓库根目录跑
```

39 个用例，重点盯三处「错了不会当场报错」的：路径穿越、分页边界、多语言回落。

---

## 二、M2 平台服务（NestJS，规划）

NestJS 10 + Mongoose + Swagger + passport-jwt，**直接以 `totalclaw-skill-shop/api` 为骨架复制**，替换领域模块。

### 模块

| 模块 | 来源 | 说明 |
|---|---|---|
| `mcp/` | 新写 | `mcp_servers` 集合：清单全文 + 探测快照 + 统计；搜索/详情/recipe/files/categories/bundles |
| `registry/` | 新写 | 从 Git 仓库（`registry/`）同步：`node-cron` 每日 + webhook 触发；生成 `/registry.json` 快照并用 Ed25519 签名（私钥走 `REGISTRY_SIGNING_KEY`） |
| `orgs/` | 新写 | 企业：私有清单、org key（M3）、成员角色 |
| `events/` | 新写 | 安装遥测，按 `(serverId, day)` 聚合 |
| `auth/` `users/` | skill-shop 复制 | SSO：`WEB_AUTH_BASE` 代理登录，`JWT_SECRET` 共享，`tc_token` cookie |
| `developer/` `admin/` | skill-shop 复制 | 上传 → `reviewStatus` → `verified` / `featured` |
| `entitlements/` `activation-codes/` `orders/` | skill-shop 复制 | 付费条目（M3 再启用） |

### Schema（`mcp_servers`）

```ts
@Schema({ timestamps: true, collection: 'mcp_servers' })
export class McpServer {
  @Prop({ required: true, unique: true, index: true }) serverId: string;   // totalclaw-mcp/<cat>/<name>
  @Prop({ required: true, unique: true, index: true }) name: string;
  @Prop({ required: true }) displayName: string;
  @Prop() description?: string;  @Prop() descriptionZh?: string;
  @Prop({ required: true }) version: string;
  @Prop() author?: string;  @Prop() license?: string;  @Prop() homepage?: string;
  @Prop({ index: true }) category: string;
  @Prop({ type: [String], default: [], index: true }) tags: string[];
  @Prop({ type: [String], default: [] }) transports: string[];
  @Prop({ type: [String], default: [] }) launchers: string[];
  @Prop({ type: Object, required: true }) manifest: Record<string, unknown>;   // mcp.yaml 全文
  @Prop({ type: Array, default: [] }) tools: { name: string; description?: string; read_only?: boolean; input_schema?: object }[];
  @Prop({ type: Object }) security?: { scan_verdict: string; prompt_injection_findings: string[]; osv: string; egress: string[] };
  @Prop({ type: Array, default: [] }) files: { path: string; sha256: string; size: number }[];
  @Prop() bundleSha256: string;
  @Prop({ default: false, index: true }) verified: boolean;
  @Prop({ default: false, index: true }) featured: boolean;
  /** 'official' | 'community' | 'developer' | 'org' */
  @Prop({ default: 'official', index: true }) ownership: string;
  @Prop({ type: Types.ObjectId, ref: 'Org', index: true, sparse: true }) orgId?: Types.ObjectId;
  @Prop({ default: 'n/a', index: true }) reviewStatus: string;
  @Prop({ type: { downloads: Number, installs: Number, probeOk: Number, probeFail: Number, ratingAvg: Number, ratingCount: Number },
          default: { downloads: 0, installs: 0, probeOk: 0, probeFail: 0, ratingAvg: 0, ratingCount: 0 } })
  stats: Record<string, number>;
  @Prop() syncedAt?: Date;
}
```

### 环境变量

`MONGODB_URI` · `JWT_SECRET` · `WEB_AUTH_BASE` · `COOKIE_DOMAIN` · `REGISTRY_REPO`（默认 `https://gitee.com/jlzdyx/totalclaw-mcp.git`）· `REGISTRY_SIGNING_KEY`（Ed25519 私钥 PEM）· `SYNC_CRON`（`0 3 * * *`）· `API_PORT`（3101）· `PUBLIC_ORIGIN`（`https://mcp.taituai.com`）

### 启动

```bash
cp .env.example .env && npm i && npm run start:dev   # :3101，Swagger /api/docs
```
