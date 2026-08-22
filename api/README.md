# api/ — 平台服务（M2）

NestJS 10 + Mongoose + Swagger + passport-jwt，**直接以 `totalclaw-skill-shop/api` 为骨架复制**，替换领域模块。

## 模块

| 模块 | 来源 | 说明 |
|---|---|---|
| `mcp/` | 新写 | `mcp_servers` 集合：清单全文 + 探测快照 + 统计；搜索/详情/recipe/files/categories/bundles |
| `registry/` | 新写 | 从 Git 仓库（`registry/`）同步：`node-cron` 每日 + webhook 触发；生成 `/registry.json` 快照并用 Ed25519 签名（私钥走 `REGISTRY_SIGNING_KEY`） |
| `orgs/` | 新写 | 企业：私有清单、org key（M3）、成员角色 |
| `events/` | 新写 | 安装遥测，按 `(serverId, day)` 聚合 |
| `auth/` `users/` | skill-shop 复制 | SSO：`WEB_AUTH_BASE` 代理登录，`JWT_SECRET` 共享，`tc_token` cookie |
| `developer/` `admin/` | skill-shop 复制 | 上传 → `reviewStatus` → `verified` / `featured` |
| `entitlements/` `activation-codes/` `orders/` | skill-shop 复制 | 付费条目（M3 再启用） |

## Schema（`mcp_servers`）

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

## 环境变量

`MONGODB_URI` · `JWT_SECRET` · `WEB_AUTH_BASE` · `COOKIE_DOMAIN` · `REGISTRY_REPO`（默认 `https://gitee.com/jlzdyx/totalclaw-mcp.git`）· `REGISTRY_SIGNING_KEY`（Ed25519 私钥 PEM）· `SYNC_CRON`（`0 3 * * *`）· `API_PORT`（3101）· `PUBLIC_ORIGIN`（`https://mcp.taituai.com`）

## 启动

```bash
cp .env.example .env && npm i && npm run start:dev   # :3101，Swagger /api/docs
```
