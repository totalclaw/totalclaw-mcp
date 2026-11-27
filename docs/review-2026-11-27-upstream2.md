# 未审核条目静态审核结果（2026-11-27）

由 `scripts/review_static.py` 生成，逐条明细 `.json` 只留在审核机本地（不入库），人工复核结论见 `-manual.json`。

## 怎么审的

只做静态审核：**没有安装、没有运行任何一个第三方包**。

- **包与版本**：npm / PyPI 上包存在、钉的版本存在、未弃用 / 未撤回（yanked）；压缩包按注册中心记录的 sha512 / sha256 校验。
- **来源**：GitHub 仓库能打开（改名的按跳转后的地址算）；条目写的仓库与包元数据里的仓库一致（同一 owner 下改名不算不一致）；仓库的 package.json / pyproject.toml 声明了同名包，或 README 提到这个包名（防冒名）。
- **许可证**：包元数据 → 包内 LICENSE 文件 → 仓库 LICENSE；商业许可、`SEE LICENSE IN` 指向非开源文本的算警告。条目没写的从元数据补上。
- **代码**：发布的压缩包下载到内存里逐文件扫（不落盘、不解压、不执行）：安装期脚本（pre/post/install、setup.py、自定义构建后端、启动即执行的 .pth）、下载即执行（curl | sh、iwr | iex、base64 解码进 shell）、读 SSH 私钥 / 浏览器 Cookie / 钱包、可疑外传端点与匿名隧道、整体外传环境变量、解码后执行、硬编码公网 IP、混淆器特征、预编译二进制、已知投毒特征（ClawHavoc 假前置安装与投放地址）、工具描述里的提示注入话术。README / PKG-INFO / METADATA / Dockerfile / CI 配置不扫（npx / uvx 不会执行它们）。命中的每一条都人工读过代码，确认无害的记在 `-manual.json` 里。
- **漏洞**：osv.dev 查钉的版本，HIGH / CRITICAL 拒绝，其余警告。
- **热度**：最近一次发布超过 2 年、或周下载量低于 20（每天不到 3 次，基本只剩镜像 / 爬虫流量）的，警告。
- **远程端点**：必须 HTTPS；端点域名与条目主页 / 仓库组织对得上，或条目引用的仓库 README 写明了这个域名；不带凭据 GET 能连上（401 / 405 也算），走代理失败时直连再试。

判定：全部无问题 → 通过（清单置 `verified: true`、`scan_verdict: allow`）；有疑点 → 警告（`warn`，保持未审核）；包 / 版本不存在、装错包、越界的下载执行行为、高危漏洞、端点不是 MCP 服务 → 拒绝（`block`，安装器永不安装）。拿不准的一律归警告。

**没覆盖到的**：运行时动态生成的工具描述与实际出网域名（要真跑起来才查得到，所以 `prompt_injection_findings` / `egress` 没写）；间接依赖（只审了包本身）；预编译二进制的行为；远程端点背后的服务端代码。

## 统计

| 运行方式 | 通过 | 警告 | 拒绝 | 合计 |
|---|---|---|---|---|
| npx | 22 | 0 | 0 | 22 |
| uvx | 7 | 0 | 0 | 7 |
| 合计 | 29 | 0 | 0 | 29 |

## 逐条结果

| 条目 | 方式 | 包 / 端点 | 结论 | 理由 |
|---|---|---|---|---|
| actors | npx | `@apify/actors-mcp-server@0.22.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| aiven | npx | `mcp-aiven@1.21.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| anymd | npx | `@sylphx/anymd@8.5.14` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bestax | npx | `bestax-mcp@1.18.88` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| brave_search | npx | `@brave/brave-search-mcp-server@2.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| contextstream | npx | `@contextstream/mcp-server@1.0.88` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| davinci_resolve | npx | `davinci-resolve-mcp@5.4.0` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
| dsh_novel_writer | npx | `dsh-novel-writer@8.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| exa_2 | npx | `exa-mcp-server@3.5.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| firecrawl | npx | `firecrawl-mcp@3.41.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gitlab | npx | `@zereight/mcp-gitlab@2.3.30` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kordoc | npx | `kordoc@4.25.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mailkite | npx | `@mailkite/mcp@0.20.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mastergo | npx | `@mastergo/magic-mcp@0.2.22` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
| mongodb_lens | npx | `mongodb-lens@9.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ms_365 | npx | `@softeria/ms-365-mcp-server@0.190.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| n8n | npx | `n8n-mcp@2.103.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| search1api | npx | `search1api-mcp@0.13.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| speakai | npx | `@speakai/mcp-server@2.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| supabase_2 | npx | `@supabase/mcp-server-supabase@0.19.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| toolbox_sdk | npx | `@toolbox-sdk/server@1.18.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| yuque | npx | `yuque-mcp@1.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| atlassian | uvx | `mcp-atlassian==0.24.7` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
| bernstein | uvx | `bernstein==4.0.0` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
| excel_haris_musa | uvx | `excel-mcp-server==2.3.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| keboola | uvx | `keboola-mcp-server==1.120.1` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
| openhire | uvx | `openhire==0.8.75` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
| opik | uvx | `opik-mcp==3.0.12` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| zotero | uvx | `zotero-mcp-server==0.17.3` | 通过 | 升级复核（2026-11-27）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同（规则与文件一一对应），无新增发现；发布者与源码仓库未变；旧版已人工复核通过。 |
