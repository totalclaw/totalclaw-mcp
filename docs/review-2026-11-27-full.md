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
| binary | 0 | 25 | 0 | 25 |
| http | 115 | 8 | 5 | 128 |
| npx | 244 | 74 | 0 | 318 |
| totalclaw | 0 | 2 | 0 | 2 |
| uvx | 105 | 44 | 1 | 150 |
| 合计 | 464 | 153 | 6 | 623 |

## 逐条结果

| 条目 | 方式 | 包 / 端点 | 结论 | 理由 |
|---|---|---|---|---|
| flow_horustek | http | `https://flow.horustek.pro/mcp` | 拒绝 | TLS 证书校验失败：[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1016) |
| maxstat | http | `https://maxstat.ru/api/mcp` | 拒绝 | TLS 证书校验失败：[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1016) |
| morningstar | http | `https://mcp.morningstar.cn/mcp` | 拒绝 | TLS 证书校验失败：[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain (_ssl.c:1016) |
| unreal_engine | http | `http://127.0.0.1:8000/mcp` | 拒绝 | 端点不是 HTTPS |
| xiaohongshu | http | `http://localhost:18060/mcp` | 拒绝 | 端点不是 HTTPS |
| didlogic | uvx | `didlogic_mcp==1.0.4` | 拒绝 | 版本 1.0.4 已被撤回（yanked）：deleting |
| awesun | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| baidu_netdisk | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| canva | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| dingtalk | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| feishu | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| gitee | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| github | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| imap_mail | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| jiandaoyun | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| jinshuju | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| linear | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| moka | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| notion | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| qcc | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tapd | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tencent_cloudbase | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tencent_edgeone | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tencent_ioa | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tencent_map | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tencent_survey | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tencent_tchouse_c | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| tianyancha | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| topview | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| web | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| wecom | binary | `None` | 警告 | 条目有多个运行时，本脚本只审第一个；启动方式 binary 不在本次静态审核范围 |
| fazhi_law | http | `https://bizveris.kuaicha365.com/law_agent/mcp` | 警告 | 端点连不上：TimeoutError The read operation timed out |
| kdocs | http | `https://mcp-center.wps.cn/skill_hub/mcp` | 警告 | 端点连不上：TimeoutError The read operation timed out |
| kuaicha_search | http | `https://bizveris.kuaicha365.com/mcp` | 警告 | 端点连不上：TimeoutError The read operation timed out |
| manto | http | `https://manto.xin/mcp` | 警告 | 端点返回 404，地址可能已变更 |
| novada | http | `https://mcp.novada.com/mcp` | 警告 | 端点连不上：_ssl.c:999: The handshake operation timed out |
| openchainbench | http | `https://openchainbench.com/api/mcp/mcp` | 警告 | 端点连不上：_ssl.c:999: The handshake operation timed out |
| remotearc | http | `https://mcp.remotearc.app/mcp` | 警告 | 端点域名 mcp.remotearc.app 与主页 / 仓库（https://github.com/yaohuangguan/remote-arc）对不上，需人工核对 |
| youshu_bd_mate | http | `https://open.yscredit.com/ys-mcp/report` | 警告 | 端点返回 500（服务端错误） |
| agentrpc | npx | `agentrpc@0.0.16` | 警告 | 周下载量很低（13） |
| agentwarden_cli | npx | `agentwarden-cli@0.3.7` | 警告 | 代码命中「下载即执行(curl\|sh)」：package/dist/rules/commands.js；代码命中「可疑外传端点」：package/dist/rules/exfiltration.js |
| alipay | npx | `@alipay/mcp-server-alipay@2.0.0` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里；许可证不是开源许可证：See license in https://ds.alipay.com/fd-ifz2dlhv/index.html |
| amap_maps | npx | `@amap/amap-maps-mcp-server@0.0.8` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里 |
| apifox | npx | `apifox-mcp-server@0.0.18` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里 |
| apple_events | npx | `mcp-server-apple-events@1.6.2` | 警告 | 有安装期执行的脚本 postinstall: node scripts/postinstall.mjs；包内含预编译二进制（静态看不到行为）：package/bin/event |
| apple_notes | npx | `@ailenshen/apple-notes-mcp@2.0.2` | 警告 | 包内含预编译二进制（静态看不到行为）：package/AppleNotesMCP.app/Contents/MacOS/AppleNotesMCP |
| baidu_map | npx | `@baidumap/mcp-server-baidu-map@1.0.5` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里 |
| bear | npx | `bear-mcp-server@1.0.0` | 警告 | 周下载量很低（14） |
| bitcoin | npx | `bitcoin-mcp@0.0.6` | 警告 | 该版本已被作者标记弃用：Package no longer supported. Contact Support at https://www.npmjs.com/support for more info. |
| boltpatternhq | npx | `boltpatternhq-mcp@1.0.0` | 警告 | 周下载量很低（16） |
| bugsnag | npx | `bugsnag-mcp-server@1.1.0` | 警告 | 源码仓库 github.com/yourusername/bugsnag-mcp 访问不到（404）；条目写的仓库 tgeselle/bugsnag-mcp 与包元数据里的仓库 yourusername/bugsnag-mcp 不一致；仓库 yourusername/bugsnag-mcp 的清单文件和 README 里都找不到包名 bugsnag-mcp-server，无法确认包出自此仓库；没有找到开源许可证声明 |
| buywhere | npx | `@buywhere/mcp-server@0.4.0` | 警告 | 源码仓库 github.com/BuyWhere/buywhere-mcp 访问不到（404）；仓库 BuyWhere/buywhere-mcp 的清单文件和 README 里都找不到包名 @buywhere/mcp-server，无法确认包出自此仓库 |
| cabal_hunter | npx | `cabal-hunter-mcp@1.0.5` | 警告 | 源码仓库 github.com/paulf280-ui/cabal-hunter-mcp 访问不到（404）；仓库 paulf280-ui/cabal-hunter-mcp 的清单文件和 README 里都找不到包名 cabal-hunter-mcp，无法确认包出自此仓库 |
| cal | npx | `cal-mcp@1.0.6` | 警告 | 周下载量很低（17） |
| clojars_deps | npx | `clojars-deps-server@0.2.0` | 警告 | 周下载量很低（19） |
| cnb | npx | `@cnbcool/mcp-server@0.6.7` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里（元数据写的是 https://cnb.cool/cnb/tools/cnb-mcp-server） |
| concord | npx | `@concord-ai/concord-mcp@0.23.0` | 警告 | 代码命中「下载即执行(curl\|sh)」：package/dist/config/install-mode.js |
| cos | npx | `cos-mcp@1.0.15` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里（元数据写的是 /） |
| davinci_resolve | npx | `davinci-resolve-mcp@5.3.4` | 警告 | 代码命中「下载即执行(curl\|sh)」：package/src/utils/media_analysis.py |
| dcs_cloud | npx | `dcs-cloud-mcp-server@2.0.3` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里；没有找到开源许可证声明 |
| desktop_commander | npx | `@wonderwhy-er/desktop-commander@0.3.4` | 警告 | 有安装期执行的脚本 postinstall: node dist/track-installation.js && node dist/npm-scripts/verify-ripgrep.js \|\| node -e "process.exit(0)" |
| egc | npx | `@egchq/egc@1.1.25` | 警告 | 有安装期执行的脚本 preinstall: node scripts/preinstall.js；代码命中「读取 SSH 私钥」：package/scripts/hooks/cursor-guardian-adapter.js；代码命中「读取 SSH 私钥」：package/scripts/lib/doctor-hooks.js；代码命中「下载即执行(curl\|sh)」：package/.opencode/dist/plugins/lib/egc-plugin-core.js；代码命中「下载即执行(curl\|sh)」：package/scripts/preinstall.js；代码命中「读取 SSH 私钥」：package/mcp/servers/egc-guardian/build/validator-narrow-target.js；代码命中「浏览器凭据 / Cookie 库」：package/mcp/servers/egc-guardian/build/validator-protected-paths.js；代码命中「读取 SSH 私钥」：package/mcp/servers/egc-guardian/build/validator.js；代码命中「读取 SSH 私钥」：package/scripts/hooks/windsurf-guardian-adapter.js；代码命中「下载即执行(curl\|sh)」：package/.opencode/plugins/lib/egc-plugin-core.ts |
| excel_negokaz | npx | `@negokaz/excel-mcp-server@0.12.0` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里；包内含预编译二进制（静态看不到行为）：package/dist/excel-mcp-server_darwin_amd64_v1/excel-mcp-server, package/dist/excel-mcp-server_darwin_arm64_v8.0/excel-mcp-server, package/dist/excel-mcp-server_linux_386_sse2/excel-mcp-server 等 8 个 |
| exchangerate | npx | `@nusantara-ventures/exchangerate-mcp@0.2.2` | 警告 | 周下载量很低（19） |
| fencescan | npx | `fencescan@0.1.4` | 警告 | 周下载量很低（12） |
| fetcher | npx | `fetcher-mcp@0.4.1` | 警告 | 有安装期执行的脚本 postinstall: playwright install chromium |
| file_merger | npx | `@exoticknight/mcp-file-merger@1.0.1` | 警告 | 周下载量很低（12） |
| forevervm | npx | `forevervm-mcp@0.1.35` | 警告 | 仓库 jamsocket/forevervm 的清单文件和 README 里都找不到包名 forevervm-mcp，无法确认包出自此仓库 |
| genieacs | npx | `genieacs-mcp@0.4.2` | 警告 | 有安装期执行的脚本 postinstall: node postinstall.js |
| github_enterprise | npx | `@ddukbg/github-enterprise-mcp@1.3.0` | 警告 | 周下载量很低（8） |
| gmail_autoauth | npx | `@gongrzhe/server-gmail-autoauth-mcp@1.1.11` | 警告 | 源码仓库 github.com/gongrzhe/server-gmail-autoauth-mcp 访问不到（404）；仓库 gongrzhe/server-gmail-autoauth-mcp 的清单文件和 README 里都找不到包名 @gongrzhe/server-gmail-autoauth-mcp，无法确认包出自此仓库 |
| goldprice | npx | `@nusantara-ventures/goldprice-mcp@0.2.1` | 警告 | 周下载量很低（14） |
| graphql_schema | npx | `mcp-graphql-schema@0.0.2` | 警告 | 周下载量很低（11） |
| headless_gmail | npx | `@peakmojo/mcp-server-headless-gmail@0.1.0` | 警告 | 周下载量很低（12） |
| hotnews | npx | `@wopal/mcp-server-hotnews@0.2.0` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里 |
| image_gen | npx | `@gongrzhe/image-gen-server@1.0.1` | 警告 | 源码仓库 github.com/GongRzhe/image-gen-server 访问不到（404）；仓库 GongRzhe/image-gen-server 的清单文件和 README 里都找不到包名 @gongrzhe/image-gen-server，无法确认包出自此仓库 |
| infimind_video | npx | `@infimind/video-mcp-cli@1.0.15` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里 |
| installer | npx | `@anaisbetts/mcp-installer@0.5.0` | 警告 | 最近一次发布在 2024-11-26，已超过 2 年没更新 |
| jarp | npx | `jarp-mcp@1.0.4` | 警告 | 周下载量很低（13） |
| kubectl | npx | `kubectl-mcp-server@2.0.0` | 警告 | 有安装期执行的脚本 postinstall: node bin/postinstall.js |
| linear_jerhadf | npx | `linear-mcp-server@0.1.0` | 警告 | 源码仓库 github.com/modelcontextprotocol/linear-server 访问不到（404）；条目写的仓库 jerhadf/linear-mcp-server 与包元数据里的仓库 modelcontextprotocol/linear-server 不一致；仓库 modelcontextprotocol/linear-server 的清单文件和 README 里都找不到包名 linear-mcp-server，无法确认包出自此仓库 |
| linear_tacticlaunch | npx | `@tacticlaunch/mcp-linear@1.4.6` | 警告 | 有安装期执行的脚本 postinstall: node -e "try { require('fs').chmodSync('./dist/index.js', '755') } catch (e) {}" |
| lingshu_solver | npx | `lingshu-solver@1.0.25` | 警告 | 许可证不是开源许可证：Proprietary |
| local | npx | `@awareness.market/local@0.22.1` | 警告 | 有安装期执行的脚本 postinstall: node install-transformers.mjs |
| makehq | npx | `@makehq/mcp-server@0.5.0` | 警告 | 源码仓库 github.com/integromat/make-mcp-server 访问不到（404）；仓库 integromat/make-mcp-server 的清单文件和 README 里都找不到包名 @makehq/mcp-server，无法确认包出自此仓库 |
| markdownify | npx | `mcp-markdownify-server@1.1.0` | 警告 | 有安装期执行的脚本 preinstall: node preinstall.js |
| mastergo | npx | `@mastergo/magic-mcp@0.2.20` | 警告 | 条目有多个运行时，本脚本只审第一个；代码命中「提示注入话术」：package/dist/index.js |
| mcp_brave_search | npx | `@modelcontextprotocol/server-brave-search@0.6.2` | 警告 | 该版本已被作者标记弃用：Package no longer supported. Contact Support at https://www.npmjs.com/support for more info.；仓库 modelcontextprotocol/servers-archived 的清单文件和 README 里都找不到包名 @modelcontextprotocol/server-brave-search，无法确认包出自此仓库 |
| mcp_everything | npx | `@modelcontextprotocol/server-everything@2.3.1` | 警告 | 许可证不是开源许可证：SEE LICENSE IN LICENSE |
| mcp_filesystem | npx | `@modelcontextprotocol/server-filesystem@2.4.0` | 警告 | 许可证不是开源许可证：SEE LICENSE IN LICENSE |
| mcp_memory | npx | `@modelcontextprotocol/server-memory@2.2.1` | 警告 | 许可证不是开源许可证：SEE LICENSE IN LICENSE |
| mcp_postgres | npx | `@modelcontextprotocol/server-postgres@0.6.2` | 警告 | 该版本已被作者标记弃用：Archived and unmaintained; no security guarantees. See https://github.com/modelcontextprotocol/servers-archived；仓库 modelcontextprotocol/servers-archived 的清单文件和 README 里都找不到包名 @modelcontextprotocol/server-postgres，无法确认包出自此仓库 |
| mcp_sequential_thinking | npx | `@modelcontextprotocol/server-sequential-thinking@2.2.0` | 警告 | 仓库 modelcontextprotocol/servers 的清单文件和 README 里都找不到包名 @modelcontextprotocol/server-sequential-thinking，无法确认包出自此仓库；许可证不是开源许可证：SEE LICENSE IN LICENSE |
| memory | npx | `@mnemoverse/mcp-memory-server@0.18.1` | 警告 | 代码命中「提示注入话术」：package/dist/errors.js；代码命中「提示注入话术」：package/dist/tools.js |
| mobilebuildmcp | npx | `mobilebuildmcp@2.7.1` | 警告 | 包内含预编译二进制（静态看不到行为）：package/bundled/axe, package/bundled/Frameworks/FBControlCore.framework/Versions/A/FBControlCore, package/bundled/Frameworks/FBDeviceControl.framework/Versions/A/FBDeviceControl 等 5 个 |
| observatory | npx | `@kryptosai/mcp-observatory@1.50.1` | 警告 | 有安装期执行的脚本 postinstall: node scripts/postinstall.mjs；代码命中「下载即执行(curl\|sh)」：package/dist/src/checks/skill-scan.js；代码命中「可疑外传端点」：package/dist/src/checks/skill-scan.js；代码命中「提示注入话术」：package/examples/insecure-mcp-server/server.mjs |
| open_apps | npx | `@2nd1st/open-mcp-apps@0.10.1` | 警告 | 代码命中「下载即执行(curl\|sh)」：package/install.mjs；代码命中「下载即执行(curl\|sh)」：package/uninstall.mjs；代码命中「下载即执行(curl\|sh)」：package/install.sh |
| open_websearch | npx | `open-websearch@2.2.0` | 警告 | 代码命中「硬编码公网 IP 地址」：package/build/test/test-redirect-safety.js；代码命中「硬编码公网 IP 地址」：package/build/test/test-url-safety.js |
| output_firewall | npx | `mcp-output-firewall@0.3.0` | 警告 | 代码命中「读取 SSH 私钥」：package/lib/adversarial.js；代码命中「提示注入话术」：package/lib/adversarial.js；代码命中「下载即执行(curl\|sh)」：package/lib/demo.js；代码命中「提示注入话术」：package/lib/demo.js；代码命中「解码后执行」：package/lib/demo.js；代码命中「可疑外传端点」：package/lib/egress.js |
| platform | npx | `@flowcore/platform-mcp-server@1.7.1` | 警告 | 没有找到开源许可证声明 |
| restcsv | npx | `restcsv-mcp-server@1.0.1` | 警告 | 周下载量很低（8） |
| safari | npx | `safari-mcp@2.24.1` | 警告 | 有安装期执行的脚本 postinstall: node scripts/postinstall.cjs \|\| true；代码命中「读取 SSH 私钥」：package/safari.js；包内含预编译二进制（静态看不到行为）：package/safari-helper |
| scan | npx | `mcp-scan@2.3.0` | 警告 | 代码命中「读取 SSH 私钥」：package/action/dist/action.cjs；代码命中「可疑外传端点」：package/action/dist/action.cjs；代码命中「提示注入话术」：package/action/dist/action.cjs；代码命中「读取 SSH 私钥」：package/dist/lib.cjs；代码命中「可疑外传端点」：package/dist/lib.cjs；代码命中「提示注入话术」：package/dist/lib.cjs；代码命中「可疑外传端点」：package/dist/chunk-7ZMUJDIA.js；代码命中「读取 SSH 私钥」：package/dist/chunk-XO4OO5AB.js；代码命中「提示注入话术」：package/dist/chunk-XO4OO5AB.js；代码命中「读取 SSH 私钥」：package/dist/lib.js；代码命中「可疑外传端点」：package/dist/lib.js；代码命中「提示注入话术」：package/dist/lib.js |
| screenpipe | npx | `screenpipe-mcp@0.20.4` | 警告 | 许可证不是开源许可证：Proprietary |
| socialcrawl | npx | `socialcrawl-mcp@2.2.0` | 警告 | 条目写的仓库 socialcrawl/mcp 与包元数据里的仓库 RidioDevelopment/socialcrawl-mcp 不一致；代码命中「下载即执行(curl\|sh)」：package/dist/data/examples.js；代码命中「PowerShell 下载即执行」：package/dist/data/examples.js |
| starknet | npx | `@mcpdotdirect/starknet-mcp-server@1.0.3` | 警告 | 代码命中「可疑外传端点」：package/build/http-server.js；代码命中「可疑外传端点」：package/build/index.js |
| summarizer | npx | `mcp-summarizer@1.0.0-alpha.2` | 警告 | 没有找到开源许可证声明；周下载量很低（9） |
| task_master_ai | npx | `task-master-ai@0.43.1` | 警告 | 代码命中「下载即执行(curl\|sh)」：package/dist/profiles-CvDnJeks.js |
| triage | npx | `mcp-triage@0.2.0` | 警告 | 周下载量很低（17） |
| trieve | npx | `trieve-mcp-server@0.1.3` | 警告 | 周下载量很低（18） |
| webresearch | npx | `@mzxrai/mcp-webresearch@0.1.7` | 警告 | 有安装期执行的脚本 postinstall: playwright install chromium |
| weisheng_scrm | npx | `mcp-server-weisheng-scrm@0.0.7` | 警告 | 找不到 GitHub 源码仓库，无法核对包出自哪里；没有找到开源许可证声明 |
| xcodebuildmcp | npx | `xcodebuildmcp@2.7.0` | 警告 | 包内含预编译二进制（静态看不到行为）：package/bundled/axe, package/bundled/Frameworks/FBControlCore.framework/Versions/A/FBControlCore, package/bundled/Frameworks/FBDeviceControl.framework/Versions/A/FBDeviceControl 等 5 个 |
| playwright-py | totalclaw | `None` | 警告 | 启动方式 totalclaw 不在本次静态审核范围 |
| wechat-desktop | totalclaw | `None` | 警告 | 启动方式 totalclaw 不在本次静态审核范围 |
| admapix | uvx | `admapix-mcp==1.0.0` | 警告 | 代码命中「下载即执行(curl\|sh)」：admapix_mcp-1.0.0/install.sh |
| apple_music_playlists | uvx | `apple-music-playlists==1.6.1` | 警告 | 代码命中「浏览器凭据 / Cookie 库」：am_playlist.py；代码命中「浏览器凭据 / Cookie 库」：apple_music_playlists-1.6.1/am_playlist.py |
| atlassian | uvx | `mcp-atlassian==0.24.6` | 警告 | 代码命中「硬编码公网 IP 地址」：mcp_atlassian-0.24.6/tests/unit/utils/test_urls.py |
| basic_memory | uvx | `basic-memory==1.0.0` | 警告 | 代码命中「下载即执行(curl\|sh)」：basic_memory/cli/commands/hook.py；代码命中「PowerShell 下载即执行」：basic_memory/cli/commands/hook.py；代码命中「下载即执行(curl\|sh)」：basic_memory-1.0.0/integrations/openclaw/index.ts；代码命中「下载即执行(curl\|sh)」：basic_memory-1.0.0/integrations/openclaw/scripts/setup-bm.sh；代码命中「下载即执行(curl\|sh)」：basic_memory-1.0.0/src/basic_memory/cli/commands/hook.py；代码命中「PowerShell 下载即执行」：basic_memory-1.0.0/src/basic_memory/cli/commands/hook.py；代码命中「读取 SSH 私钥」：basic_memory-1.0.0/tests/mcp/test_tool_bm_read.py；代码命中「读取 SSH 私钥」：basic_memory-1.0.0/tests/services/test_project_service.py；代码命中「读取 SSH 私钥」：basic_memory-1.0.0/tests/utils/test_validate_project_path.py |
| bernstein | uvx | `bernstein==3.24.1` | 警告 | 代码命中「下载即执行(curl\|sh)」：bernstein/adapters/claude.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/cursor.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/devin_terminal.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/droid.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/forge.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/goose.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/junie.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/mistral.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/muse.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/ollama.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/opencode.py；代码命中「下载即执行(curl\|sh)」：bernstein/adapters/plandex.py；代码命中「可疑外传端点」：bernstein/core/notifications/sinks/discord.py；代码命中「读取 SSH 私钥」：bernstein/core/observability/behavior_anomaly.py；代码命中「可疑外传端点」：bernstein/core/observability/behavior_anomaly.py；代码命中「读取 SSH 私钥」：bernstein/core/protocols/ssh_backend.py；代码命中「硬编码公网 IP 地址」：bernstein/core/protocols/acp/handlers.py；代码命中「下载即执行(curl\|sh)」：bernstein/core/security/auto_approve.py；代码命中「解码进 shell」：bernstein/core/security/auto_approve.py；代码命中「下载即执行(curl\|sh)」：bernstein/core/security/command_allowlist.py；代码命中「提示注入话术」：bernstein/core/security/owasp_asi_detectors.py；代码命中「提示注入话术」：bernstein/core/tokens/prompt_injection.py；代码命中「可疑外传端点」：bernstein/core/tunnels/drivers/bore.py；代码命中「可疑外传端点」：bernstein/core/tunnels/drivers/cloudflared.py；代码命中「提示注入话术」：bernstein/eval/scenario_generator.py；代码命中「可疑外传端点」：bernstein/gui/pwa.py；代码命中「可疑外传端点」：bernstein-3.24.1/examples/plugins/discord_notifier.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/claude.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/cursor.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/devin_terminal.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/droid.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/forge.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/goose.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/junie.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/mistral.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/muse.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/ollama.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/opencode.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/adapters/plandex.py；代码命中「可疑外传端点」：bernstein-3.24.1/src/bernstein/core/notifications/sinks/discord.py；代码命中「读取 SSH 私钥」：bernstein-3.24.1/src/bernstein/core/observability/behavior_anomaly.py；代码命中「可疑外传端点」：bernstein-3.24.1/src/bernstein/core/observability/behavior_anomaly.py；代码命中「读取 SSH 私钥」：bernstein-3.24.1/src/bernstein/core/protocols/ssh_backend.py；代码命中「硬编码公网 IP 地址」：bernstein-3.24.1/src/bernstein/core/protocols/acp/handlers.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/core/security/auto_approve.py；代码命中「解码进 shell」：bernstein-3.24.1/src/bernstein/core/security/auto_approve.py；代码命中「下载即执行(curl\|sh)」：bernstein-3.24.1/src/bernstein/core/security/command_allowlist.py；代码命中「提示注入话术」：bernstein-3.24.1/src/bernstein/core/security/owasp_asi_detectors.py；代码命中「提示注入话术」：bernstein-3.24.1/src/bernstein/core/tokens/prompt_injection.py；代码命中「可疑外传端点」：bernstein-3.24.1/src/bernstein/core/tunnels/drivers/bore.py；代码命中「可疑外传端点」：bernstein-3.24.1/src/bernstein/core/tunnels/drivers/cloudflared.py；代码命中「提示注入话术」：bernstein-3.24.1/src/bernstein/eval/scenario_generator.py；代码命中「可疑外传端点」：bernstein-3.24.1/src/bernstein/gui/pwa.py |
| code_graph_rag | uvx | `code-graph-rag==0.7.1` | 警告 | 代码命中「读取 SSH 私钥」：codebase_rag/constants/security.py；代码命中「读取 SSH 私钥」：code_graph_rag-0.7.1/codebase_rag/constants/security.py |
| coding_tools | uvx | `coding-tools-mcp==0.5.0` | 警告 | 代码命中「可疑外传端点」：mcp_desktop_client/runtime.py；代码命中「可疑外传端点」：mcp_desktop_client/locales/app_zh_CN.qm；代码命中「可疑外传端点」：mcp_desktop_client/locales/app_zh_CN.ts；代码命中「可疑外传端点」：coding_tools_mcp-0.5.0/apps/desktop-client/mcp_desktop_client/locales/app_zh_CN.qm；代码命中「可疑外传端点」：coding_tools_mcp-0.5.0/apps/desktop-client/mcp_desktop_client/locales/app_zh_CN.ts；代码命中「可疑外传端点」：coding_tools_mcp-0.5.0/apps/desktop-client/mcp_desktop_client/runtime.py；代码命中「可疑外传端点」：coding_tools_mcp-0.5.0/tests/test_desktop_client.py |
| dolphindb | uvx | `dolphindb-mcp-server==0.1.0` | 警告 | 没有找到开源许可证声明；周下载量很低（10） |
| ds | uvx | `mcp-server-ds==0.1.5` | 警告 | 有安装期执行的脚本 setup.py: setup.py 含 subprocess；代码命中「下载即执行(curl\|sh)」：mcp_server_ds-0.1.5/setup.py |
| duckduckgo | uvx | `duckduckgo-mcp-server==0.7.0` | 警告 | 代码命中「硬编码公网 IP 地址」：duckduckgo_mcp_server/test_server.py；代码命中「硬编码公网 IP 地址」：duckduckgo_mcp_server-0.7.0/src/duckduckgo_mcp_server/test_server.py |
| dy_xhs | uvx | `douyin-mcp-server==1.2.1` | 警告 | 条目写的仓库 AshinH/dy-xhs-mcp-server 与包元数据里的仓库 yzfly/douyin-mcp-server 不一致 |
| flameox | uvx | `flameox==0.2.9` | 警告 | 代码命中「整体外传环境变量」：flameox-0.2.9/tests/test_provider_preparation.py；包内含预编译二进制（静态看不到行为）：flameox-0.2.9/mcp-publisher |
| for_blender | uvx | `mcp-for-blender==2.3.1` | 警告 | 代码命中「读取 SSH 私钥」：mcp_for_blender-2.3.1/tests/test_image_input_security.py |
| friday_memory | uvx | `friday-memory==1.5.2` | 警告 | 周下载量很低（5） |
| ip2location_io | uvx | `mcp-ip2location-io==1.1.2` | 警告 | 周下载量很低（18） |
| jobson_xhs | uvx | `jobson-xhs-mcp==0.1.1` | 警告 | 周下载量很低（17） |
| keboola | uvx | `keboola-mcp-server==1.120.0` | 警告 | 代码命中「可疑外传端点」：keboola_mcp_server/resources/flow_examples/conditional_flow_examples.jsonl |
| knowlyr_datacheck | uvx | `knowlyr-datacheck==0.5.1` | 警告 | 周下载量很低（11） |
| knowlyr_sandbox | uvx | `knowlyr-sandbox==0.1.2` | 警告 | 周下载量很低（14） |
| mcp_sqlite | uvx | `mcp-server-sqlite==2025.4.25` | 警告 | 仓库 modelcontextprotocol/servers-archived 的清单文件和 README 里都找不到包名 mcp-server-sqlite，无法确认包出自此仓库 |
| mcptoon | uvx | `mcptoon==0.8.40` | 警告 | 代码命中「提示注入话术」：mcptoon/router.py；代码命中「提示注入话术」：mcptoon-0.8.40/src/mcptoon/router.py；代码命中「提示注入话术」：mcptoon-0.8.40/tests/test_openapi.py；代码命中「提示注入话术」：mcptoon-0.8.40/tests/test_router.py；代码命中「硬编码公网 IP 地址」：mcptoon-0.8.40/tests/test_serve_perf.py；代码命中「提示注入话术」：mcptoon-0.8.40/tests/test_v02_features.py；代码命中「提示注入话术」：mcptoon-0.8.40/tests/test_v073_http_security.py |
| mem0 | uvx | `mem0-mcp-server==0.2.1` | 警告 | 源码仓库 github.com/mem0-ai/mem0-mcp-server 访问不到（404）；条目写的仓库 mem0ai/mem0-mcp 与包元数据里的仓库 mem0-ai/mem0-mcp-server 不一致；仓库 mem0-ai/mem0-mcp-server 的清单文件和 README 里都找不到包名 mem0-mcp-server，无法确认包出自此仓库 |
| opendal | uvx | `mcp-server-opendal==0.2.0` | 警告 | 周下载量很低（13） |
| openhire | uvx | `openhire==0.8.73` | 警告 | 代码命中「下载即执行(curl\|sh)」：openhire/doctor.py；代码命中「PowerShell 下载即执行」：openhire/doctor.py；代码命中「提示注入话术」：openhire/mcp_server.py；代码命中「下载即执行(curl\|sh)」：openhire/pages/connect.html；代码命中「PowerShell 下载即执行」：openhire/pages/connect.html；代码命中「下载即执行(curl\|sh)」：openhire-0.8.73/docs/connect.html；代码命中「PowerShell 下载即执行」：openhire-0.8.73/docs/connect.html；代码命中「下载即执行(curl\|sh)」：openhire-0.8.73/src/openhire/doctor.py；代码命中「PowerShell 下载即执行」：openhire-0.8.73/src/openhire/doctor.py；代码命中「提示注入话术」：openhire-0.8.73/src/openhire/mcp_server.py；代码命中「下载即执行(curl\|sh)」：openhire-0.8.73/src/openhire/pages/connect.html；代码命中「PowerShell 下载即执行」：openhire-0.8.73/src/openhire/pages/connect.html；代码命中「硬编码公网 IP 地址」：openhire-0.8.73/tests/test_ssrf_guard.py |
| openosint | uvx | `openosint==2.38.2` | 警告 | 代码命中「下载即执行(curl\|sh)」：openosint/agent.py；代码命中「下载即执行(curl\|sh)」：openosint/cli.py；代码命中「下载即执行(curl\|sh)」：openosint-2.38.2/openosint/agent.py；代码命中「下载即执行(curl\|sh)」：openosint-2.38.2/openosint/cli.py；代码命中「硬编码公网 IP 地址」：openosint-2.38.2/tests/test_web_server_ssrf.py |
| oura | uvx | `oura-mcp-server==0.1.3` | 警告 | 源码仓库 github.com/tomek-korbak/oura-mcp-server 访问不到（404）；条目写的仓库 tomekkorbak/oura-mcp-server 与包元数据里的仓库 tomek-korbak/oura-mcp-server 不一致；仓库 tomek-korbak/oura-mcp-server 的清单文件和 README 里都找不到包名 oura-mcp-server，无法确认包出自此仓库 |
| piia_engram | uvx | `piia-engram==4.27.0` | 警告 | 代码命中「读取 SSH 私钥」：piia_engram-4.27.0/tests/test_core.py；代码命中「读取 SSH 私钥」：piia_engram-4.27.0/tests/test_export_redaction.py；代码命中「读取 SSH 私钥」：piia_engram-4.27.0/tests/test_hook_content_digest.py；代码命中「硬编码公网 IP 地址」：piia_engram-4.27.0/tests/test_reader_ssrf.py；代码命中「提示注入话术」：piia_engram-4.27.0/tests/test_resume_brief_v3_30.py |
| playwright_blackwhite084 | uvx | `playwright-server==0.2.1` | 警告 | 周下载量很低（9） |
| rememberizer | uvx | `mcp-server-rememberizer==0.1.6` | 警告 | 周下载量很低（10） |
| roundtable_ai | uvx | `roundtable-ai==0.8.0` | 警告 | 代码命中「下载即执行(curl\|sh)」：claudable_helper/cli/adapters/cursor_agent.py；代码命中「下载即执行(curl\|sh)」：roundtable_ai-0.8.0/claudable_helper/cli/adapters/cursor_agent.py |
| serena_agent | uvx | `serena-agent==2.1.0` | 警告 | 代码命中「下载即执行(curl\|sh)」：solidlsp/language_servers/lean4_language_server.py；代码命中「下载即执行(curl\|sh)」：serena_agent-2.1.0/src/solidlsp/language_servers/lean4_language_server.py |
| since_cutoff | uvx | `since-cutoff==0.5.0` | 警告 | 代码命中「下载即执行(curl\|sh)」：since_cutoff-0.5.0/tests/test_review_fixes.py |
| starrocks | uvx | `mcp-server-starrocks==0.4.0` | 警告 | 审核过程出错：URLError: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1016)> |
| timeplus | uvx | `mcp-timeplus==0.1.6` | 警告 | 周下载量很低（7） |
| timeserver | uvx | `MCP-timeserver==0.1.0` | 警告 | 周下载量很低（19） |
| tinybird | uvx | `mcp-tinybird==1.0.3` | 警告 | 周下载量很低（16） |
| unichat | uvx | `unichat-mcp-server==0.2.21` | 警告 | 周下载量很低（15） |
| video_editor | uvx | `video-editor-mcp==0.1.59` | 警告 | 没有找到开源许可证声明；包内含预编译二进制（静态看不到行为）：video_editor_mcp-0.1.59/video-player/downloader, video_editor_mcp-0.1.59/video-player/open-window, video_editor_mcp-0.1.59/video-player/vj-player 等 65 个 |
| vikingdb | uvx | `mcp-server-vikingdb==0.1.2` | 警告 | 没有找到开源许可证声明；周下载量很低（9） |
| wireshark | uvx | `wireshark-mcp==4.0.0` | 警告 | 代码命中「硬编码公网 IP 地址」：wireshark_mcp-4.0.0/scripts/agent_eval_harness.py |
| ws | uvx | `ws-mcp==0.1.11` | 警告 | 没有找到开源许可证声明；周下载量很低（9） |
| x | uvx | `x-mcp==0.1.0` | 警告 | 周下载量很低（5） |
| zoom_search | uvx | `zoom-search==0.1.6` | 警告 | 周下载量很低（13） |
| zotero | uvx | `zotero-mcp-server==0.17.2` | 警告 | 代码命中「下载即执行(curl\|sh)」：zotero_mcp_server-0.17.2/plugin/src/zotero/doctor.ts；代码命中「提示注入话术」：zotero_mcp_server-0.17.2/plugin/test/live/translate.live.ts；代码命中「可疑外传端点」：zotero_mcp_server-0.17.2/tests/test_http_host_origin_guard.py |
| actablesite | http | `https://actablesite.com/mcp/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| ads | http | `https://mcp-ads.com/mcp-slim` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| agentaos | http | `https://mcp.agentaos.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| aitoearn | http | `https://aitoearn.ai/api/ai/agent/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| alphavantage | http | `https://mcp.alphavantage.co/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| archive_hospital_mcp | http | `https://bingli.tengmed.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| axiomlab | http | `https://axiomlab.online/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| bazhuayu | http | `https://mcp.bazhuayu.com?includeTools=search_templates,execute_task,get_task_status,export_data,search_tasks,start_or_stop_task` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| better_design | http | `https://better-design.com/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| bibigpt | http | `https://bibigpt.co/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| bugly_token | http | `https://bugly.tds.qq.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| call4 | http | `https://call4.me/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| callmemcp | http | `https://callmemcp.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| camscanner_mcp | http | `https://ai-tools.camscanner.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| chainflip_broker | http | `https://chainflip-broker.io/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| chuhaijiang | http | `https://mcp.gateway.chuhaijiang.com/mcp/oauth` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| cisp_mcp | http | `https://cisp.zenitera.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| developertoolkit | http | `https://developertoolkit.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| dknowc_mcp | http | `https://mcp.dknowc.cn/s6/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| docs_qq | http | `https://docs.qq.com/openapi/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| episkeyai | http | `https://mcp.episkeyai.com/groksearch_rs/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| eulerpool | http | `https://api.eulerpool.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| exa | http | `https://mcp.exa.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| ezjoin_meeting | http | `https://www.ezyjoin.cn/api/mcp/message` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| fadada_richee | http | `https://claw.richee.cn/claw-api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| fanruan_growth_advisor | http | `https://www.mossdo.com/api/v1/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| fbs_connector | http | `https://api2.u3w.com/fbs-mcp/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| finenter | http | `https://mcp-server-global.comein.cn/mcp-servers/mcp-server-brm/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| firstdata_deepminer_com | http | `https://firstdata.deepminer.com.cn/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| flova | http | `https://service.flova.tv/api/mcp/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| formquote_chen_yu_d1_workers | http | `https://formquote-mcp.chen-yu-d1.workers.dev/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| fyopen_lawsearch | http | `https://api.cjbdi.com:8443/354347/mcp_law_service` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| gangtise_mcp | http | `https://openapi.gangtise.com/application/open-mcp/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| gaodun_job | http | `https://apigateway.gaodun.com/dyson/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| getengram | http | `https://mcp.getengram.app/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| getyoutubetranscript | http | `https://getyoutubetranscript.com/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| gildata | http | `https://api.gildata.com/mcp-servers/aidata-assistant-srv-tool?token=${GILDATA_TOKEN}` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| githubcopilot | http | `https://api.githubcopilot.com/mcp/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| gongyi_open_mcp | http | `https://ssl.gongyi.qq.com/gygw-web/api/open/tob/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| gwmcp_lkcoffee | http | `https://gwmcp.lkcoffee.com/order/user/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| hack123_henryht | http | `https://hack123.henryht.sh/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| homouniversalis | http | `https://homouniversalis.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| hpsilab | http | `https://hpsilab.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| huggingface | http | `https://huggingface.co/mcp?login` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| ima_mcp | http | `https://ima.qq.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| jiushuyun | http | `https://work.jiushuyun.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| kling_ai_plugin | http | `https://klingai.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| kling_ai_plugin_ai | http | `https://kling.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| landed | http | `https://mcp.landed.jobs/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| lexiang | http | `https://mcp.lexiang-app.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| lingxing_mcp | http | `https://openmcp.lingxing.com/mcp-servers/lingxing-mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| linkfox_product_selection | http | `https://mcp-tool-gateway.linkfox.com/mcp/any-tool` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| magichour | http | `https://mcp.magichour.ai/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| marketnow | http | `https://marketnow.site/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| meeting_tencent | http | `https://mcp.meeting.tencent.com/mcp/wemeet-open/v1` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| membase | http | `https://api.app.membase.com/mcp-http` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| motomarks | http | `https://motomarks.io/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| mx_ds_mcp | http | `https://mxapi.eastmoney.com/mxds/v2/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| mzl_trademark | http | `https://www.mozlen.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| needhave | http | `https://needhave.io/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| neo_crm | http | `https://mcp.xiaoshouyi.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| openany | http | `https://mcp.openany.si/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| opendata | http | `https://mcp.isjike.com/mcp-servers/opendata/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| openshorts | http | `https://mcp.openshorts.app/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| pandadata | http | `https://pandadatamcp.pandaaiquant.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| pangolinfo | http | `https://mcp.pangolinfo.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| parallelstudio_app_store_review_intellig | http | `https://parallelstudio--app-store-review-intelligence-mcp.apify.actor/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| parallelstudio_youtube_transcripts_apify | http | `https://parallelstudio--youtube-transcripts-mcp.apify.actor/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| picset_commerce_images | http | `https://picsetai.cn/functions/v1/agent-mcp-v1/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| picset_video_generation | http | `https://picsetai.cn/functions/v1/agent-video-mcp-v1/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| pkulaw | http | `https://apim-gateway.pkulaw.com/mcp-law-agg/1.0.0/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| posy | http | `https://posy.page/api/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| proboost | http | `https://mcp.microdata-inc.com/mcp-servers/proboost-tiktok-amazon-patent-mcp/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| qcc_legal | http | `https://agent.qcc.com/mcp/legal/stream` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| qixinhuiyan_mcp | http | `https://mcp.qixin.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| qrdx | http | `https://mcp.qrdx.dev/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| readgzh | http | `https://api.readgzh.site/mcp-server` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| remcp | http | `https://remcp.site/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| roboparts | http | `https://roboparts.cc/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| runcomfy | http | `https://mcp.runcomfy.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| salesnail_instructor | http | `https://sn.long-arena.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| salestouch | http | `https://touch.long-arena.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| scalekit | http | `https://mcp.scalekit.com/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| sentry_getsentry | http | `https://mcp.sentry.dev/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| shanglv_mcp_gateway | http | `https://mcp-gateway.yql.net/mcp/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| skills_wondel | http | `https://skills.wondel.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| sq_company_dynamic | http | `https://api.chanyedata.com/mcp/c3f5924cc60dbe1729f5cc332e627304/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| squirrelscan | http | `https://mcp.squirrelscan.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| stripe | http | `https://mcp.stripe.com` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| supabase | http | `https://mcp.supabase.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| supermemory | http | `https://mcp.supermemory.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| talivia | http | `https://talivia.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tanyuan_assistant | http | `https://api.tanyuan.qq.com/wb/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tdx_connector | http | `https://txmcp.tdx.com.cn:3001/txmcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| teacher_assistant | http | `https://aiteach.qq.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tec_do | http | `https://tec-chi-external-skill-mcp.tec-do.cn/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tencent_qidian_cs | http | `https://sse.qidian.qq.com/qidian-cs/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tencent_weiyun | http | `https://www.weiyun.com/api/v3/mcpserver` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| terraform | http | `https://mcp.terraform.io/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tongzhou_fin_research | http | `https://mcp-gateway.textmind-gz.com/mcp/tongzhou-research` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| topview_canvas | http | `https://mcp-browser.topview.ai` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| topview_official | http | `https://mcp.topview.ai/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tplus_api | http | `https://mcphub.chanapp.chanjet.com/151/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| transcriptapi | http | `https://transcriptapi.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tryunsora | http | `https://mcp.tryunsora.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| tweetapi | http | `https://mcp.tweetapi.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| uizze | http | `https://uizze.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| westock_mcp | http | `https://stockbuddy.qq.com/cgi/cgi-bin/openai/mcp/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| wkinfo | http | `https://mcp.wkinfo.com.cn/mcp-servers/integrated/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| worklittle | http | `https://mcp.worklittle.com/` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| xingtu_claw_risk | http | `https://claw-mcp.tcredit.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| yingmi_mcp | http | `https://stargate.yingmi.com/mcp/v2?apiKey=${YINGMI_API_KEY}` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| you | http | `https://api.you.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| yuandian_mcp | http | `https://open.chineselaw.com/mcp` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| yzf_invoice_mcp_server | http | `https://super-ai-app.yunzhangfang.com/api/mcp/invoice/stream` | 通过 | HTTPS、域名与厂商对得上、端点可连通 |
| 12306 | npx | `12306-mcp@0.3.10` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| 5dive | npx | `@5dive/mcp@0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| actors | npx | `@apify/actors-mcp-server@0.21.12` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| agent | npx | `@taisly/agent@0.2.10` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| agent_recall | npx | `agent-recall-mcp@3.5.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| agentgate | npx | `mcp-agentgate@0.67.61` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| agentql | npx | `agentql-mcp@1.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| agentset | npx | `@agentset/mcp@1.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ai_art_engine | npx | `ai-art-engine-mcp@8.9.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ai_economics | npx | `@michalpiszczek/ai-economics-mcp@1.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ai_price | npx | `ai-price-mcp@1.5.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| airbnb | npx | `@openbnb/mcp-server-airbnb@0.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| airtable | npx | `airtable-mcp-server@1.14.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| airtable_rashidazarang | npx | `@rashidazarang/airtable-mcp@5.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| aiven | npx | `mcp-aiven@1.20.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| alibabacloud_dataworks | npx | `alibabacloud-dataworks-mcp-server@1.0.45` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| amazon_bedrock | npx | `@zxkane/mcp-server-amazon-bedrock@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| anilist | npx | `anilist-mcp@1.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| any_chat_completions | npx | `@pyroprompts/any-chat-completions-mcp@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| anymd | npx | `@sylphx/anymd@8.5.13` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| apifox_wangmhaha | npx | `@wangmhaha/apifox-mcp-server@1.7.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| apple | npx | `@dhravya/apple-mcp@0.2.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| apple_docs_2_0 | npx | `apple-docs-2.0-mcp@3.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| apple_shortcuts | npx | `mcp-server-apple-shortcuts@1.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| aria_icons | npx | `aria-icons@0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| asana | npx | `@roychri/mcp-server-asana@1.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| aseprite_ai_artist | npx | `@pebbly/aseprite-ai-artist@0.8.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| attio | npx | `attio-mcp-server@0.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| awwwards | npx | `awwwards-mcp@1.22.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| azure_devops | npx | `@tiberriver256/mcp-server-azure-devops@0.1.54` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| balldontlie | npx | `balldontlie-mcp@0.6.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bandcamp | npx | `bandcamp-mcp@0.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| beat_browser | npx | `@beatapi/beat-browser@1.4.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bestax | npx | `bestax-mcp@1.18.79` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bhived | npx | `bhived-mcp@1.4.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bigquery | npx | `@ergut/mcp-bigquery-server@1.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bilibili | npx | `@xzxzzx/bilibili-mcp@1.14.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bilibili_js | npx | `bilibili-mcp-js@0.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| blazephoenix | npx | `@blazephoenix/mcp@1.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| blockhand | npx | `@gjlmotea/blockhand-mcp@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| box | npx | `box-mcp-server@0.3.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| brave_search | npx | `@brave/brave-search-mcp-server@2.1.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| brightdata | npx | `@brightdata/mcp@4.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| browser_kit | npx | `@mcp-browser-kit/server@11.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| browser_tools | npx | `@agentdeskai/browser-tools-mcp@2.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| browsermcp | npx | `@browsermcp/mcp@2.5.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| canli_validation | npx | `canli-validation-mcp@0.16.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| castov | npx | `castov@1.7.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| central_bank | npx | `@allratestoday/central-bank-mcp@0.3.19` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| chinese_text_tools | npx | `chinese-text-tools@1.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| chrome_devtools | npx | `chrome-devtools-mcp@1.13.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cli_wong2 | npx | `@wong2/mcp-cli@2.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| clipugc | npx | `clipugc@1.4.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cloakbrowser | npx | `cloakbrowser-mcp@1.15.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cloudflare | npx | `@cloudflare/mcp-server-cloudflare@0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cloudgpu | npx | `cloudgpu-mcp@0.16.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cnstock | npx | `@wilshi/cnstock@0.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| code_relay | npx | `code-relay-mcp@3.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| codewiki | npx | `codewiki-mcp@1.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| codex | npx | `@codex-data/codex-mcp@0.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| coincap | npx | `coincap-mcp@0.9.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| confluent | npx | `@confluentinc/mcp-confluent@1.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| context7 | npx | `@upstash/context7-mcp@4.7.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| contextfetch | npx | `@contextfetch/mcp@1.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| contextstream | npx | `@contextstream/mcp-server@1.0.83` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| crawlbrulee | npx | `@crawlbrulee/mcp@2.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dart | npx | `dart-mcp-server@0.2.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| data_studio | npx | `@geek-fun/data-studio-mcp@0.1.12` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dawnmere_connector | npx | `dawnmere-connector@0.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dchub | npx | `dchub-mcp-server@2.12.59` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| desearch | npx | `desearch-mcp-server@0.12.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dexpaprika | npx | `dexpaprika-mcp@2.9.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dingtalk_open | npx | `dingtalk-mcp@1.1.21` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dinox | npx | `@deepdataspace/dinox-mcp@1.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dnstwist | npx | `@burtthecoder/mcp-dnstwist@1.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dsh_novel_writer | npx | `dsh-novel-writer@7.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| duckduckgo_zhsama | npx | `duckduckgo-mcp-server@0.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| dumplingai | npx | `mcp-server-dumplingai@1.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| edgeone_pages | npx | `edgeone-pages-mcp@0.0.16` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| engine_dj | npx | `engine-dj-mcp@0.18.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| engram_rs | npx | `engram-rs-mcp@0.14.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| everything2mcp | npx | `everything2mcp@0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| evm | npx | `@mcpdotdirect/evm-mcp-server@2.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| exa_2 | npx | `exa-mcp-server@3.4.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| exit1 | npx | `exit1-mcp@0.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| faxforagents | npx | `faxforagents-mcp@0.5.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| feeling_search | npx | `feeling-search-mcp@0.2.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| feishu_2 | npx | `feishu-mcp@0.3.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| fetch | npx | `mcp-fetch-server@1.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ffmpeg_skill | npx | `ffmpeg-skill@4.8.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| figma_developer | npx | `figma-developer-mcp@0.13.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| figwright | npx | `@figwright/mcp@0.7.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| find | npx | `@agentage/find-mcp@1.13.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| finlight | npx | `finlight-mcp@1.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| firebase | npx | `@gannonh/firebase-mcp@1.4.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| firecrawl | npx | `firecrawl-mcp@3.40.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| flomo | npx | `mcp-server-flomo@0.0.11` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| footballcharts | npx | `footballcharts-mcp@0.7.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| forge | npx | `@reliantlabs/forge@1.11.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| freeaudiototext | npx | `freeaudiototext-mcp@1.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| frontrun | npx | `frontrun-mcp-server@2.8.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| genclass | npx | `@genclass/mcp@0.2.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ghcard | npx | `@ghcardhq/ghcard@0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| giphy | npx | `mcp-server-giphy@1.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gitee_oschina | npx | `@gitee/mcp-gitee@1.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| github_atomicmail | npx | `@atomicmail/mcp-github@0.3.34` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gitlab | npx | `@zereight/mcp-gitlab@2.3.29` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| godot | npx | `@coding-solo/godot-mcp@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| google_calendar | npx | `@takumi0706/google-calendar-mcp@2.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| google_news | npx | `@chanmeng666/google-news-server@1.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| google_search | npx | `@adenot/mcp-google-search@0.3.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gotohuman | npx | `@gotohuman/mcp-server@0.2.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| graphlit | npx | `graphlit-mcp-server@1.0.20260112001` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| graphql | npx | `mcp-graphql@2.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| hackmd | npx | `hackmd-mcp@1.5.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| hfspace | npx | `@llmindset/mcp-hfspace@0.5.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| hushvert | npx | `@hushvert/mcp@0.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| hyperbrowser | npx | `hyperbrowser-mcp@1.0.25` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| image_compression | npx | `@inhiblab-core/mcp-image-compression@0.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| influxdb | npx | `influxdb-mcp-server@0.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| interactive | npx | `interactive-mcp@1.10.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ipfs | npx | `mcp-ipfs@0.1.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| iterm | npx | `iterm-mcp@1.2.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| jev_use | npx | `jev-use@0.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| jshook | npx | `@jshookmcp/jshook@0.4.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| json | npx | `@gongrzhe/server-json-mcp@1.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| juzpost_cli | npx | `juzpost-cli@0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kibela | npx | `@kj455/mcp-kibela@0.3.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kilo_kit | npx | `@vodailocz/kilo-kit-mcp@1.9.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kordoc | npx | `kordoc@4.25.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kubernetes | npx | `mcp-server-kubernetes@4.2.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kubernetes_containers | npx | `kubernetes-mcp-server@0.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| leetcode | npx | `@jinzcdev/leetcode-mcp-server@1.5.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| livetennisapi | npx | `livetennisapi-mcp@1.6.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| lockdocs | npx | `@sylphx/lockdocs@0.7.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| lucyd | npx | `@lucyd/mcp@0.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| lystbot | npx | `lystbot@0.4.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| magic | npx | `@21st-dev/magic@0.2.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| maigret | npx | `mcp-maigret@1.0.22` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mailkite | npx | `@mailkite/mcp@0.20.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| memgit | npx | `memgit-mcp@0.16.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| miro | npx | `@llmindset/mcp-miro@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| miro_k_jarzyna | npx | `@k-jarzyna/mcp-miro@1.0.11` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mnemosyne_os | npx | `@mnemosyne_os/mcp@2.5.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mobile | npx | `@mobilenext/mobile-mcp@1.0.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| model_salt | npx | `@modelsalt/model-salt@1.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongo | npx | `mcp-mongo-server@3.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongo_quantgeekdev | npx | `mongo-mcp@0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongodb | npx | `mongodb-mcp-server@3.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mongodb_lens | npx | `mongodb-lens@9.1.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ms_365 | npx | `@softeria/ms-365-mcp-server@0.187.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| multiverse | npx | `@lamemind/mcp-server-multiverse@1.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mysql_benborla29 | npx | `@benborla29/mcp-server-mysql@2.0.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mysql_f4ww4z | npx | `@f4ww4z/mcp-mysql-server@0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mysql_legacy | npx | `mysql-legacy-mcp@0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| n8n | npx | `n8n-mcp@2.103.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| nationalparks | npx | `mcp-server-nationalparks@1.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| naver_search | npx | `@isnow890/naver-search-mcp@1.0.55` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| nocodb | npx | `nocodb-mcp-server@1.0.24` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| notion_notionhq | npx | `@notionhq/notion-mcp-server@2.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| notion_suekou | npx | `@suekou/mcp-notion-server@2.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ns | npx | `ns-mcp-server@0.1.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ns_private_access | npx | `@johnneerdael/ns-private-access-mcp@6.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| octeract_context | npx | `octeract-context@4.9.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| octocrawl | npx | `@octocrawl/mcp@0.8.13` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| omophub | npx | `@omophub/omophub-mcp@1.6.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| onchain | npx | `@bankless/onchain-mcp@1.0.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| opanel | npx | `opanel-mcp@0.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| openai | npx | `@mzxrai/mcp-openai@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| openapi_schema | npx | `mcp-openapi-schema@0.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| palisadeemail | npx | `@palisadeemail/mcp@0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| perplexity_ai | npx | `@perplexity-ai/mcp-server@1.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| phonedriver | npx | `phonedriver@0.1.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| pixelbolt | npx | `pixelbolt@0.21.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| playwright | npx | `@playwright/mcp@0.0.86` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| playwright_automatalabs | npx | `@automatalabs/mcp-server-playwright@1.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| playwright_executeautomation | npx | `@executeautomation/playwright-mcp-server@1.0.12` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| pluggedin_proxy | npx | `@pluggedin/pluggedin-mcp-proxy@3.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| plushsource | npx | `plushsource-mcp@0.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| posteverywhere | npx | `@posteverywhere/mcp@1.14.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| probe_kit | npx | `mcp-probe-kit@4.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| proxy | npx | `@jetbrains/mcp-proxy@1.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| proxy_toolkit | npx | `@ipvolt/proxy-toolkit-mcp@0.3.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| quickchart | npx | `@gongrzhe/quickchart-mcp-server@1.0.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| rad_security | npx | `@rad-security/mcp-server@0.0.49` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| rag_web_browser | npx | `@apify/mcp-server-rag-web-browser@0.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| recall | npx | `@fainir/recall@0.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ref_tools | npx | `ref-tools-mcp@3.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| replicate | npx | `mcp-replicate@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| replicate_flux | npx | `replicate-flux-mcp@0.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| repomap | npx | `@sylphx/repomap@1.9.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| reqlan | npx | `@reqlan/mcp@0.13.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| rijksmuseum | npx | `mcp-server-rijksmuseum@1.0.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| screenshotone | npx | `@screenshotone/mcp@1.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| search1api | npx | `search1api-mcp@0.12.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| searxng | npx | `mcp-searxng@2.11.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| secret_design | npx | `secret-design-mcp@0.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| security_audit | npx | `mcp-security-audit@1.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| sentry | npx | `@sentry/mcp-server@0.50.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| serato_dj | npx | `serato-dj-mcp@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shadcn_ui | npx | `@jpisnice/shadcn-ui-mcp-server@3.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shodan | npx | `@burtthecoder/mcp-shodan@1.0.41` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shunshi_bazi | npx | `shunshi-bazi-mcp@0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shunshi_kangxi | npx | `shunshi-kangxi-mcp@0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| sidehand | npx | `sidehand@0.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| sightradar | npx | `sightradar-mcp@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| snaprender | npx | `snaprender-mcp@1.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| speakai | npx | `@speakai/mcp-server@2.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| strava | npx | `@r-huijts/strava-mcp-server@1.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| studio_sidecar | npx | `@gjlmotea/studio-sidecar-mcp@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| supabase_2 | npx | `@supabase/mcp-server-supabase@0.18.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| supercarto | npx | `supercarto@0.7.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tapetide | npx | `tapetide-mcp@1.0.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| taskade | npx | `@taskade/mcp-server@0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tasty_agent | npx | `tasty-agent@7.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tavily | npx | `tavily-mcp@0.2.22` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tavily_mcptools | npx | `@mcptools/mcp-tavily@1.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| telegram | npx | `@chaindead/telegram-mcp@0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| threatcluster | npx | `threatcluster-mcp@0.2.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tiktok | npx | `tiktok-mcp@0.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| todoist | npx | `@abhiz123/todoist-mcp-server@0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tomba | npx | `@tomba-io/tomba-mcp-server@1.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| toolbox_sdk | npx | `@toolbox-sdk/server@1.17.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tools | npx | `@signet-auth/mcp-tools@0.10.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| transcriptdock | npx | `@transcriptdock/mcp@0.1.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| transcriptfetch | npx | `transcriptfetch-mcp@0.3.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| typescribe | npx | `mcp-typescribe@0.8.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| unblockingapi | npx | `@unblockingapi/mcp@0.9.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| vectorize | npx | `@vectorize-io/vectorize-mcp-server@0.4.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| vibe_check | npx | `@pv-bhat/vibe-check-mcp@2.7.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| vicem_cli | npx | `vicem-cli@1.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| virustotal | npx | `@burtthecoder/mcp-virustotal@1.0.40` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| voyp | npx | `voyp-mcp@0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| vrchat | npx | `vrchat-mcp@0.15.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| webclaw | npx | `@webclaw/mcp@0.7.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| wenyan_md | npx | `@wenyan-md/mcp@2.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| whois | npx | `@bharathvaj/whois-mcp@1.0.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| wiro | npx | `@wiro-ai/wiro-mcp@2.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| yepcode | npx | `@yepcode/mcp-server@1.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| youtube | npx | `@anaisbetts/mcp-youtube@0.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| youtube_transcript | npx | `@kimtaeyoon83/mcp-server-youtube-transcript@0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| yuque | npx | `yuque-mcp@1.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| zotero_kaliaboi | npx | `mcp-zotero@1.0.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| zubeid_youtube | npx | `zubeid-youtube-mcp-server@1.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| adb_mysql | uvx | `adb-mysql-mcp-server==2.0.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| adbpg | uvx | `adbpg-mcp-server==2.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| adls2 | uvx | `adls2-mcp-server==0.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| alchemy | uvx | `mcp-alchemy==2026.10.15.202659` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| alloy_engine | uvx | `alloy-engine==0.1.10` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ancestry | uvx | `mcp-server-ancestry==0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| arxiv | uvx | `arxiv-mcp-server==0.8.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| arxiv_latex | uvx | `arxiv-latex-mcp==0.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| backlink_guard | uvx | `backlink-guard==0.12.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| bigquery_lucashild | uvx | `mcp-server-bigquery==0.3.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| calculator | uvx | `mcp-server-calculator==0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cdp_bridge | uvx | `cdp-bridge==0.1.25` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| chroma | uvx | `chroma-mcp==0.2.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| chronulus | uvx | `chronulus-mcp==0.0.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| clawtouch | uvx | `clawtouch-mcp==0.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cli | uvx | `cli-mcp-server==0.2.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| cn_commerce | uvx | `mcp-cn-commerce==0.1.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| codemcp | uvx | `codemcp==0.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| codex_control_plane | uvx | `codex-control-plane-mcp==0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| datetime | uvx | `mcp-datetime==0.3.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| docker | uvx | `docker-mcp==0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| duckdb | uvx | `mcp-server-duckdb==1.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| eda_agent | uvx | `eda-agent==0.8.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| edinet | uvx | `edinet-mcp==0.9.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| elasticsearch | uvx | `elasticsearch-mcp-server==2.1.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| elevenlabs | uvx | `elevenlabs-mcp-server==0.1.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| elevenlabs_2 | uvx | `elevenlabs-mcp==0.12.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| emulo | uvx | `emulo==0.6.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| erius_phone | uvx | `erius-phone-mcp==0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| estat | uvx | `estat-mcp==0.2.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| evc_team_relay | uvx | `evc-team-relay-mcp==1.0.10` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| everything_search | uvx | `mcp-server-everything-search==0.3.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| excel | uvx | `mcp-excel-server==1.0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| excel_haris_musa | uvx | `excel-mcp-server==2.3.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| fidelis_memory | uvx | `fidelis-memory==0.2.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gemini_pro | uvx | `gemini-pro-mcp==0.1.8` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| google_sheets | uvx | `mcp-google-sheets==0.6.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| greptimedb | uvx | `greptimedb-mcp-server==0.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| gsuite | uvx | `mcp-gsuite==0.4.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| hn | uvx | `mcp-hn==0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| home_assistant | uvx | `mcp-server-home-assistant==0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ida_pro | uvx | `ida-pro-mcp==1.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ipinfo | uvx | `mcp-server-ipinfo==0.7.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| jacobian | uvx | `jacobian==0.23.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| justfill | uvx | `justfill-mcp==0.4.10` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| jvm | uvx | `jvm-mcp-server==0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| kagimcp | uvx | `kagimcp==1.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| keystash | uvx | `keystash==0.4.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| knowlyr_modelaudit | uvx | `knowlyr-modelaudit==0.4.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| llm_context | uvx | `llm-context==0.7.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| local_gpu_imagegen | uvx | `local-gpu-imagegen==0.9.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| lrvx | uvx | `lrvx-mcp==0.12.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mac_messages | uvx | `mac-messages-mcp==1.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| marketmirror | uvx | `marketmirror==0.4.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| marketplaces_ru | uvx | `marketplaces-mcp-ru==0.7.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| markitdown | uvx | `markitdown-mcp==0.0.1a8` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcp_fetch | uvx | `mcp-server-fetch==2026.11.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcp_git | uvx | `mcp-server-git==2026.11.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcp_time | uvx | `mcp-server-time==2026.11.18` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mcpsurfr | uvx | `mcpsurfr==1.2.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| md_to_word_docx | uvx | `md-to-word-docx==3.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| minas_webdav | uvx | `minas-webdav==0.3.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mindmap | uvx | `mindmap-mcp-server==0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| minimax | uvx | `minimax-mcp==0.0.20` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| motherduck | uvx | `mcp-server-motherduck==1.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| mysql | uvx | `mysql-mcp-server==0.4.5` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| new_term_radar | uvx | `new-term-radar==0.8.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| obsidian | uvx | `mcp-obsidian==0.2.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| office_powerpoint | uvx | `office-powerpoint-mcp-server==2.0.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| office_word | uvx | `office-word-mcp-server==1.1.11` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| omx_hyperliquid | uvx | `omx-hyperliquid==0.1.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| openai_pierrebrunelle | uvx | `mcp-server-openai==0.1.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| openai_websearch | uvx | `openai-websearch-mcp==0.4.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| opik | uvx | `opik-mcp==3.0.11` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| osm | uvx | `osm-mcp-server==0.1.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| oxylabs | uvx | `oxylabs-mcp==0.10.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| ozon | uvx | `ozon-mcp-server==2.5.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| parlayapi | uvx | `parlayapi-mcp==0.3.8` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| preloop | uvx | `preloop==1.0.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| prometheus | uvx | `prometheus_mcp_server==1.6.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| python_interpreter | uvx | `mcp-python-interpreter==1.2.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| qdrant | uvx | `mcp-server-qdrant==0.8.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| redis | uvx | `redis-mcp-server==0.5.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| scrapely | uvx | `scrapely-mcp==0.3.16` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| scrapling_fetch | uvx | `scrapling-fetch-mcp==0.2.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| searxng_secretiveshell | uvx | `mcp-searxng==0.1.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| semble | uvx | `semble==0.7.3` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| semgrep | uvx | `semgrep-mcp==0.9.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| shell | uvx | `mcp-shell-server==1.1.15` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| simple_arxiv | uvx | `mcp-simple-arxiv==0.6.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| simple_openai_assistant | uvx | `mcp-simple-openai-assistant==0.4.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| simple_pubmed | uvx | `mcp-simple-pubmed==0.1.16` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| simple_timeserver | uvx | `mcp-simple-timeserver==3.3.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| singlestore | uvx | `singlestore-mcp-server==0.4.19` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| snowflake | uvx | `mcp_snowflake_server==0.4.0` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| sqlite_graph_memory | uvx | `sqlite-graph-memory==0.3.9` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| supabase_alexander_zuev | uvx | `supabase-mcp-server==0.4` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| text_editor | uvx | `mcp-text-editor==1.2.2` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| tradingview | uvx | `tradingview-mcp-server==0.8.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| usb_rea | uvx | `usb-rea==0.7.14` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| wb | uvx | `wb-mcp-server==2.6.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| wolfram_alpha | uvx | `mcp-wolfram-alpha==0.2.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| xiyan | uvx | `xiyan_mcp_server==0.1.7` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| yfmcp | uvx | `yfmcp==0.14.1` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
| zoomeye | uvx | `mcp-server-zoomeye==0.1.6` | 通过 | 元数据、仓库、许可证、包内代码与 osv 均无问题 |
