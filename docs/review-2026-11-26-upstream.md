# 未审核条目静态审核结果（2026-11-26）

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
| npx | 72 | 0 | 0 | 72 |
| uvx | 32 | 0 | 0 | 32 |
| 合计 | 104 | 0 | 0 | 104 |

## 逐条结果

| 条目 | 方式 | 包 / 端点 | 结论 | 理由 |
|---|---|---|---|---|
| actors | npx | `@apify/actors-mcp-server@0.21.12` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| agent_recall | npx | `agent-recall-mcp@3.5.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| aiven | npx | `mcp-aiven@1.20.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| anymd | npx | `@sylphx/anymd@8.5.13` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| azure_devops | npx | `@tiberriver256/mcp-server-azure-devops@0.1.54` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bestax | npx | `bestax-mcp@1.18.79` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bhived | npx | `bhived-mcp@1.4.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bilibili | npx | `@xzxzzx/bilibili-mcp@1.14.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| brave_search | npx | `@brave/brave-search-mcp-server@2.1.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| brightdata | npx | `@brightdata/mcp@4.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| browsermcp | npx | `@browsermcp/mcp@2.5.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| canli_validation | npx | `canli-validation-mcp@0.16.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| chrome_devtools | npx | `chrome-devtools-mcp@1.13.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| concord | npx | `@concord-ai/concord-mcp@0.23.0` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| context7 | npx | `@upstash/context7-mcp@4.7.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| contextstream | npx | `@contextstream/mcp-server@1.0.83` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| davinci_resolve | npx | `davinci-resolve-mcp@5.3.4` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| dchub | npx | `dchub-mcp-server@2.12.59` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dcs_cloud | npx | `dcs-cloud-mcp-server@2.0.3` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| desktop_commander | npx | `@wonderwhy-er/desktop-commander@0.3.4` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| dexpaprika | npx | `dexpaprika-mcp@2.9.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dnstwist | npx | `@burtthecoder/mcp-dnstwist@1.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dsh_novel_writer | npx | `dsh-novel-writer@7.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| egc | npx | `@egchq/egc@1.1.25` | 通过 | 升级复核（2026-11-26）：新增命中：doctor-hooks.js 构造一个指向 ~/.ssh/id_rsa 的假 Write 事件喂给自家 guardian 钩子，验证它会拦截，并不真写；egc-plugin-core 里 curl\|sh 出现在命令白名单的注释中。 |
| exa_2 | npx | `exa-mcp-server@3.4.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| fetcher | npx | `fetcher-mcp@0.4.1` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| find | npx | `@agentage/find-mcp@1.13.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| firecrawl | npx | `firecrawl-mcp@3.40.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| frontrun | npx | `frontrun-mcp-server@2.8.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| genieacs | npx | `genieacs-mcp@0.4.2` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| github_atomicmail | npx | `@atomicmail/mcp-github@0.3.34` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gitlab | npx | `@zereight/mcp-gitlab@2.3.29` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| google_news | npx | `@chanmeng666/google-news-server@1.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| infimind_video | npx | `@infimind/video-mcp-cli@1.0.15` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| jshook | npx | `@jshookmcp/jshook@0.4.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kordoc | npx | `kordoc@4.25.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kubernetes | npx | `mcp-server-kubernetes@4.2.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| leetcode | npx | `@jinzcdev/leetcode-mcp-server@1.5.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| linear_tacticlaunch | npx | `@tacticlaunch/mcp-linear@1.4.6` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| livetennisapi | npx | `livetennisapi-mcp@1.6.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| local | npx | `@awareness.market/local@0.22.1` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| lockdocs | npx | `@sylphx/lockdocs@0.7.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| maigret | npx | `mcp-maigret@1.0.22` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mastergo | npx | `@mastergo/magic-mcp@0.2.20` | 通过 | 升级复核（2026-11-26）：新增命中是 magic-mcp 工具描述里的产品使用说明（如「空页面就如实报告，不要让用户去画布」），不涉及越权或外传；发布者 jialun_yao→muzi131313 为原维护者名单内成员，自 0.2.9 起持续发布，仓库未变。 |
| memory | npx | `@mnemoverse/mcp-memory-server@0.18.1` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| mobile | npx | `@mobilenext/mobile-mcp@1.0.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongo | npx | `mcp-mongo-server@3.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongodb | npx | `mongodb-mcp-server@3.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongodb_lens | npx | `mongodb-lens@9.1.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ms_365 | npx | `@softeria/ms-365-mcp-server@0.187.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| n8n | npx | `n8n-mcp@2.103.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| naver_search | npx | `@isnow890/naver-search-mcp@1.0.55` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| notion_notionhq | npx | `@notionhq/notion-mcp-server@2.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| playwright | npx | `@playwright/mcp@0.0.86` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| rad_security | npx | `@rad-security/mcp-server@0.0.49` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| safari | npx | `safari-mcp@2.24.1` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| screenpipe | npx | `screenpipe-mcp@0.20.4` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| screenshotone | npx | `@screenshotone/mcp@1.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| search1api | npx | `search1api-mcp@0.12.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| searxng | npx | `mcp-searxng@2.11.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| sentry | npx | `@sentry/mcp-server@0.50.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shodan | npx | `@burtthecoder/mcp-shodan@1.0.41` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| socialcrawl | npx | `socialcrawl-mcp@2.2.0` | 通过 | 升级复核（2026-11-26）：新增命中是 dist/data/examples.js 里内嵌的示例数据（Bun 发版说明文本）；仓库与发布者两版一致（RidioDevelopment / ridiodevs），条目仓库不一致为旧版即有。 |
| speakai | npx | `@speakai/mcp-server@2.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| supabase_2 | npx | `@supabase/mcp-server-supabase@0.18.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| taskade | npx | `@taskade/mcp-server@0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| threatcluster | npx | `threatcluster-mcp@0.2.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| toolbox_sdk | npx | `@toolbox-sdk/server@1.17.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| transcriptfetch | npx | `transcriptfetch-mcp@0.3.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| virustotal | npx | `@burtthecoder/mcp-virustotal@1.0.40` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| webclaw | npx | `@webclaw/mcp@0.7.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| weisheng_scrm | npx | `mcp-server-weisheng-scrm@0.0.7` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| atlassian | uvx | `mcp-atlassian==0.24.6` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| basic_memory | uvx | `basic-memory==1.0.0` | 通过 | 升级复核（2026-11-26）：新增命中是单测里的路径穿越用例列表（tests/mcp/test_tool_bm_read.py），不读私钥。 |
| bernstein | uvx | `bernstein==3.24.1` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| bigquery_lucashild | uvx | `mcp-server-bigquery==0.3.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| clawtouch | uvx | `clawtouch-mcp==0.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| code_graph_rag | uvx | `code-graph-rag==0.7.1` | 通过 | 升级复核（2026-11-26）：新增命中是敏感文件黑名单（codebase_rag/constants/security.py 列 id_rsa 等以拒绝读取），属防护代码。 |
| datetime | uvx | `mcp-datetime==0.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| elasticsearch | uvx | `elasticsearch-mcp-server==2.1.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| evc_team_relay | uvx | `evc-team-relay-mcp==1.0.10` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| excel_haris_musa | uvx | `excel-mcp-server==2.3.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| for_blender | uvx | `mcp-for-blender==2.3.1` | 通过 | 升级复核（2026-11-26）：新增命中是单测（tests/test_image_input_security.py 在 tmp_path 造假私钥验证不会外传）。 |
| ipinfo | uvx | `mcp-server-ipinfo==0.7.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kagimcp | uvx | `kagimcp==1.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| keboola | uvx | `keboola-mcp-server==1.120.0` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| lrvx | uvx | `lrvx-mcp==0.12.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| marketplaces_ru | uvx | `marketplaces-mcp-ru==0.7.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcp_fetch | uvx | `mcp-server-fetch==2026.11.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcp_git | uvx | `mcp-server-git==2026.11.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcp_time | uvx | `mcp-server-time==2026.11.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcptoon | uvx | `mcptoon==0.8.40` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| minimax | uvx | `minimax-mcp==0.0.20` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| motherduck | uvx | `mcp-server-motherduck==1.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mysql | uvx | `mysql-mcp-server==0.4.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| openhire | uvx | `openhire==0.8.73` | 通过 | 升级复核（2026-11-26）：新增命中是随包文档 connect.html 里教用户安装 uv 的官方一行命令（astral.sh），不是代码执行路径。 |
| openosint | uvx | `openosint==2.38.2` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| opik | uvx | `opik-mcp==3.0.11` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| oxylabs | uvx | `oxylabs-mcp==0.10.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| piia_engram | uvx | `piia-engram==4.27.0` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
| semble | uvx | `semble==0.7.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shell | uvx | `mcp-shell-server==1.1.15` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| yfmcp | uvx | `yfmcp==0.14.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| zotero | uvx | `zotero-mcp-server==0.17.2` | 通过 | 升级复核（2026-11-26）：与已上架的旧版本逐项比对：同一扫描器在旧 pin 上命中相同，无新增发现；旧版已人工复核通过。 |
