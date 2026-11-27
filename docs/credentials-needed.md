# 需要真实凭据才能补工具清单的条目（C2.1）

由 2026-11-27 的 registry.json 生成：未下架、还没有工具清单、且需要凭据（必填环境变量，或远程端点要 OAuth / Bearer）的条目，共 263 条。
不需要凭据的 284 条已直接实探：176 条补齐工具清单，108 条起不来（另行排查，见 TODO C2.1）。

## 拿到凭据后怎么补

- 环境变量 / Bearer：`export <变量>=<值>` 后跑 `../totalclaw-agent/.venv/bin/python scripts/probe_server.py <条目名>`，会写回 `tools.json` 并重做工具描述注入扫描。
- OAuth：先 `totalclaw mcp login <条目名>` 完成授权，再同上探测。
- 补完跑 `scripts/gen_registry.py` 与 `--check --strict`。

## OAuth（装后在浏览器登录授权）（68 条）

| 状态 | 分类 | 条目 | 名称 | 需要的变量 | 申请 / 说明 |
|---|---|---|---|---|---|
| [ ] | ai | `getengram` | Engram | — | https://github.com/get-engram/engram |
| [ ] | ai | `membase` | membase-mcp | — | https://github.com/unibaseio/membase |
| [ ] | ai | `supermemory` | supermemory | — | https://github.com/supermemoryai/supermemory |
| [ ] | biz | `agentaos` | AgentaOS | — | https://github.com/AgentaOS/agentaos |
| [ ] | biz | `chuhaijiang` | 出海匠 | — | https://mcp.gateway.chuhaijiang.com |
| [ ] | biz | `fadada_richee` | 法大大睿契 | — | https://claw.richee.cn |
| [ ] | biz | `fyopen_lawsearch` | 法研·法律法规检索 | — | https://api.cjbdi.com |
| [ ] | biz | `jiushuyun` | 九数云BI | — | https://work.jiushuyun.com |
| [ ] | biz | `mzl_trademark` | 摩知轮商标查询 | — | https://www.mozlen.com |
| [ ] | biz | `neo_crm` | 销售易CRM | — | https://mcp.xiaoshouyi.com |
| [ ] | biz | `pkulaw` | 北大法宝·法律智能检索 | — | https://apim-gateway.pkulaw.com |
| [ ] | biz | `qcc_legal` | 企查查·法律数据 | — | https://agent.qcc.com |
| [ ] | biz | `salesnail_instructor` | SalesNail 讲师 | — | https://sn.long-arena.com |
| [ ] | biz | `salestouch` | SalesTouch 经营执行 | — | https://touch.long-arena.com |
| [ ] | biz | `stripe` | Stripe | — | https://docs.stripe.com/mcp |
| [ ] | biz | `tanyuan_assistant` | TDC 文化智能体 | — | https://api.tanyuan.qq.com |
| [ ] | biz | `tec_do` | Tec-Do 2.0 广告与增长情报 | — | https://tec-chi-external-skill-mcp.tec-do.cn |
| [ ] | biz | `wkinfo` | 威科先行 | — | https://mcp.wkinfo.com.cn |
| [ ] | biz | `xingtu_claw_risk` | 天创信用星图MCP | — | https://claw-mcp.tcredit.com |
| [ ] | biz | `yuandian_mcp` | 华宇元典法律数据 | — | https://open.chineselaw.com |
| [ ] | comm | `call4` | call4me | — | https://github.com/skeptrunedev/call4me |
| [ ] | comm | `ezjoin_meeting` | EzyJoin智慧会议 | — | https://www.ezyjoin.cn |
| [ ] | comm | `gongyi_open_mcp` | 腾讯公益机构服务平台 | — | https://ssl.gongyi.qq.com |
| [ ] | comm | `lexiang` | 乐享知识库 | — | https://mcp.lexiang-app.com |
| [ ] | comm | `shanglv_mcp_gateway` | 用友智能服务（AI BaaS） | — | https://mcp-gateway.yql.net |
| [ ] | comm | `tencent_qidian_cs` | 腾讯企点客服 | — | https://sse.qidian.qq.com |
| [ ] | comm | `tweetapi` | TweetAPI MCP | — | https://github.com/tweetapi/tweetapi-mcp |
| [ ] | creative | `camscanner_mcp` | 扫描全能王 | — | https://ai-tools.camscanner.com |
| [ ] | creative | `kling_ai_plugin` | Kling AI | — | https://klingai.com |
| [ ] | creative | `kling_ai_plugin_ai` | Kling AI | — | https://kling.ai |
| [ ] | data | `ads` | MCP Ads | — | https://github.com/RoyAzran/mcp-ads |
| [ ] | data | `dknowc_mcp` | 深知可信工作台 | — | https://mcp.dknowc.cn |
| [ ] | data | `finenter` | 进门投研 | — | https://mcp-server-global.comein.cn |
| [ ] | data | `morningstar` | 晨星 Morningstar | — | https://mcp.morningstar.cn |
| [ ] | data | `mx_ds_mcp` | 东方财富妙想MCP | — | https://mxapi.eastmoney.com |
| [ ] | data | `pandadata` | PandaData 金融数据 | — | https://pandadatamcp.pandaaiquant.com |
| [ ] | data | `qixinhuiyan_mcp` | 启信慧眼 | — | https://mcp.qixin.com |
| [ ] | data | `supabase` | supabase-mcp | — | https://github.com/supabase-community/supabase-mcp |
| [ ] | data | `talivia` | Talivia Agent Kit | — | https://github.com/talivia-group/agent |
| [ ] | data | `tdx_connector` | 通达信 | — | https://txmcp.tdx.com.cn |
| [ ] | data | `tongzhou_fin_research` | 同舟金融研究 | — | https://mcp-gateway.textmind-gz.com |
| [ ] | data | `westock_mcp` | 腾讯自选股 | — | https://stockbuddy.qq.com |
| [ ] | data | `yzf_invoice_mcp_server` | 云帐房AI开票 | — | https://super-ai-app.yunzhangfang.com |
| [ ] | dev | `better_design` | Better Design | — | https://github.com/marvkr/better-design |
| [ ] | dev | `githubcopilot` | github-mcp-server | — | https://github.com/github/github-mcp-server |
| [ ] | dev | `huggingface` | hf-mcp-server | — | https://github.com/huggingface/hf-mcp-server |
| [ ] | dev | `remcp` | ReMCP | — | https://github.com/getremcp/remcp |
| [ ] | dev | `sentry_getsentry` | sentry-mcp | — | https://github.com/getsentry/toolkit |
| [ ] | dev | `uizze` | UIZZE | — | https://github.com/uizze/uizze |
| [ ] | hr | `gaodun_job` | 大学生实习就业助手 | — | https://apigateway.gaodun.com |
| [ ] | hr | `teacher_assistant` | 企鹅教师助手 | — | https://aiteach.qq.com |
| [ ] | infra | `scalekit` | Scalekit MCP Server | — | https://github.com/scalekit-inc/scalekit-mcp-server |
| [ ] | infra | `tplus_api` | 畅捷通T+ | — | https://mcphub.chanapp.chanjet.com |
| [ ] | media | `bibigpt` | BibiGPT | — | https://github.com/JimmyLv/bibigpt-skill |
| [ ] | media | `openshorts` | OpenShorts | — | https://github.com/mutonby/openshorts |
| [ ] | media | `topview_canvas` | TopView Canvas 画布 MCP | — | https://www.topview.ai/canvas |
| [ ] | media | `topview_official` | TopView 官方 MCP（电商数据 + AI 生成） | — | https://www.topview.ai |
| [ ] | media | `tryunsora` | Unsora | — | https://github.com/Shipped-Studio/unsora |
| [ ] | misc | `gwmcp_lkcoffee` | 瑞幸咖啡 MCP | — | https://open.lkcoffee.com/ |
| [ ] | misc | `posy` | Posy | — | https://github.com/Himanshu-Sangshetti/posy |
| [ ] | office | `archive_hospital_mcp` | 腾讯健康全周期管理平台 | — | https://bingli.tengmed.com |
| [ ] | office | `docs_qq` | 腾讯文档 MCP | — | https://docs.qq.com/open/auth/mcp.html |
| [ ] | office | `meeting_tencent` | 腾讯会议 MCP | — | https://meeting.tencent.com/ai-skill.html |
| [ ] | office | `tencent_weiyun` | 微云 | — | https://www.weiyun.com |
| [ ] | social | `aitoearn` | AiToEarn | — | https://github.com/yikart/AiToEarn |
| [ ] | web | `bazhuayu` | 八爪鱼 | — | https://mcp.bazhuayu.com |
| [ ] | web | `landed` | Landed MCP | — | https://github.com/landedjobs/landed-mcp |
| [ ] | web | `you` | You.com | — | https://github.com/youdotcom-oss/agent-skills |

## Bearer / API Key（远程端点）（21 条）

| 状态 | 分类 | 条目 | 名称 | 需要的变量 | 申请 / 说明 |
|---|---|---|---|---|---|
| [ ] | biz | `eulerpool` | Eulerpool | — | https://eulerpool.com/financial-data-api/mcp |
| [ ] | biz | `fanruan_growth_advisor` | 帆软增长谋士 | MOSS_API_KEY | https://docs.mossdo.com/docs/function/data-resource/api |
| [ ] | biz | `pangolinfo` | pangolinfo-mcp | — | https://github.com/Pangolin-spg/pangolinfo-mcp |
| [ ] | biz | `youshu_bd_mate` | 智客AI · 对公(To B)营销助手 | API_KEY | https://open.yscredit.com/mcp/guide |
| [ ] | creative | `picset_commerce_images` | Picset AI 电商图片 | PICSET_AGENT_SK | https://picsetai.cn/profile?scene=workbuddy&ch=image |
| [ ] | creative | `picset_video_generation` | Picset AI 视频创作 | PICSET_AGENT_SK | https://picsetai.cn/profile?scene=workbuddy&ch=video |
| [ ] | creative | `unreal_engine` | Unreal Engine | — | https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor |
| [ ] | data | `maxstat` | MaxStat MCP | X_API_TOKEN | https://github.com/fbmdata/maxstat-mcp |
| [ ] | data | `parallelstudio_app_store_review_intellig` | App Store & Google Play Review Intelligence | — | https://github.com/gunnargray-dev/app-store-review-intelligence-mcp |
| [ ] | infra | `bugly_token` | Bugly 质量概览 | BUGLY_ACCESS_TOKEN | https://bugly.tds.qq.com/v2/user/token |
| [ ] | infra | `cisp_mcp` | 水滴征信 | CISP_API_KEY | https://cisp.zenitera.com/openapi |
| [ ] | infra | `terraform` | terraform-mcp-server | — | https://github.com/hashicorp/terraform-mcp-server |
| [ ] | media | `axiomlab` | Axiom Lab (官方) | — | https://github.com/Axiom-lab-tech/axiomlab-mcp |
| [ ] | media | `getyoutubetranscript` | YouTube Transcript + YouTube Search MCP | — | https://github.com/tubeagentkit/youtube-mcp |
| [ ] | media | `parallelstudio_youtube_transcripts_apify` | YouTube Transcripts MCP | — | https://github.com/gunnargray-dev/youtube-transcripts-mcp |
| [ ] | media | `runcomfy` | RunComfy (官方) | — | https://github.com/runcomfy-com/runcomfy-mcp |
| [ ] | media | `transcriptapi` | TranscriptAPI | — | https://github.com/ZeroPointRepo/youtube-mcp |
| [ ] | social | `xiaohongshu` | 小红书 | — | https://github.com/xpzouying/xiaohongshu-mcp |
| [ ] | web | `episkeyai` | GrokSearch-rs | — | https://github.com/Episkey-G/GrokSearch-rs |
| [ ] | web | `firstdata_deepminer_com` | FirstData | — | https://github.com/MLT-OSS/FirstData |
| [ ] | web | `novada` | Novada-mcp | — | https://github.com/NovadaLabs/Novada-mcp |

## 需填环境变量（本地运行）（174 条）

| 状态 | 分类 | 条目 | 名称 | 需要的变量 | 申请 / 说明 |
|---|---|---|---|---|---|
| [ ] | ai | `graphlit` | Graphlit | GRAPHLIT_ORGANIZATION_ID, GRAPHLIT_ENVIRONMENT_ID, GRAPHLIT_JWT_SECRET | https://github.com/graphlit/graphlit-mcp-server |
| [ ] | ai | `memory` | mcp-memory-server | MNEMOVERSE_API_KEY | https://github.com/mnemoverse/mcp-memory-server |
| [ ] | ai | `recall` | recall | CLAUDE_CODE | https://github.com/fainir/recall |
| [ ] | ai | `rememberizer` | Rememberizer AI | REMEMBERIZER_API_TOKEN | https://github.com/skydeckai/mcp-server-rememberizer |
| [ ] | biz | `alipay` | 支付宝 | AP_APP_ID, AP_APP_KEY, AP_PUB_KEY | https://www.npmjs.com/package/@alipay/mcp-server-alipay |
| [ ] | biz | `blazephoenix` | BlazePhoenix | BLAZEPHOENIX_RPC_BASE | https://github.com/blazephoenixxyz-crypto/blazephoenix-mcp |
| [ ] | biz | `central_bank` | central-bank-mcp | ALLRATES_API_KEY | https://github.com/AllRates-Today/central-bank-mcp |
| [ ] | biz | `codex` | codex-mcp | CODEX_API_KEY | https://github.com/Codex-Data/codex-mcp |
| [ ] | biz | `estat` | estat-mcp | ESTAT_APP_ID | https://github.com/ajtgjmdjp/estat-mcp |
| [ ] | biz | `flow_horustek` | Horus Flow Intelligence | X_RAPIDAPI_KEY | https://github.com/horustechltd/horus-flow-mcp |
| [ ] | biz | `goldprice` | goldprice.dev | GP_KEY | https://github.com/nusantara-ventures/goldprice-mcp |
| [ ] | biz | `lingxing_mcp` | 领星ERP | LINGXING_MCP_KEY | https://www.lingxing.com/help/article/mcp |
| [ ] | biz | `linkfox_product_selection` | Linkfox 选品 | LINKFOX_AGENT_API_KEY | https://skill.linkfox.com/linkfoxskills/guide.htm |
| [ ] | biz | `lucyd` | mcp-server | LUCYD_PRIVATE_KEY | https://github.com/Lucyd-trade/mcp-server |
| [ ] | biz | `onchain` | Bankless Onchain | BANKLESS_API_TOKEN | https://github.com/bankless/onchain-mcp |
| [ ] | biz | `ozon` | ozon-mcp-server | OZON_CLIENT_ID, OZON_API_KEY, DATA_DIR | https://github.com/DeviceIngineering/ozon-mcp-server |
| [ ] | biz | `tapetide` | Tapetide | TAPETIDE_TOKEN | https://github.com/Tapetide-hq/nse-bse-indian-stock-market-data-mcp |
| [ ] | biz | `tasty_agent` | tasty-agent | TASTYTRADE_CLIENT_SECRET, TASTYTRADE_REFRESH_TOKEN | https://github.com/ferdousbhai/tasty-agent |
| [ ] | biz | `wb` | wb-mcp-server | WB_API_TOKEN, DATA_DIR | https://github.com/DeviceIngineering/wb-mcp-server |
| [ ] | comm | `dingtalk_open` | 钉钉 | DINGTALK_Client_ID, DINGTALK_Client_Secret | https://github.com/open-dingtalk/dingtalk-mcp |
| [ ] | comm | `faxforagents` | Fax for Agents | FAXFORAGENTS_API_KEY | https://github.com/faxforagents/mcp |
| [ ] | comm | `google_calendar` | google-calendar-mcp | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | https://github.com/takumi0706/google-calendar-mcp |
| [ ] | comm | `gotohuman` | gotoHuman | GOTOHUMAN_API_KEY | https://github.com/gotohuman/gotohuman-mcp-server |
| [ ] | comm | `gsuite` | mcp-gsuite | ACCOUNTS_FILE, CREDENTIALS_DIR | https://github.com/MarkusPfundstein/mcp-gsuite |
| [ ] | comm | `mailkite` | MailKite | MAILKITE_API_KEY | https://github.com/mailkite/mailkite-mcp |
| [ ] | comm | `telegram` | telegram-mcp | TG_APP_ID, TG_API_HASH | https://github.com/chaindead/telegram-mcp |
| [ ] | comm | `tomba` | tomba-mcp-server | TOMBA_API_KEY, TOMBA_SECRET_KEY | https://github.com/tomba-io/tomba-mcp-server |
| [ ] | comm | `vrchat` | vrchat-mcp | VRCHAT_USERNAME, VRCHAT_AUTH_TOKEN | https://github.com/sawa-zen/vrchat-mcp |
| [ ] | comm | `x` | X (Twitter) (by vidhupv) | TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET | https://github.com/vidhupv/x-mcp |
| [ ] | creative | `anilist` | anilist-mcp | ANILIST_TOKEN | https://github.com/yuna0x0/anilist-mcp |
| [ ] | creative | `rijksmuseum` | rijksmuseum-mcp | RIJKSMUSEUM_API_KEY | https://github.com/r-huijts/rijksmuseum-mcp |
| [ ] | data | `adbpg` | Alibaba Cloud AnalyticDB for PostgreSQL | ADBPG_HOST, ADBPG_PORT, ADBPG_USER, ADBPG_PASSWORD, ADBPG_DATABASE | https://github.com/aliyun/alibabacloud-adbpg-mcp-server |
| [ ] | data | `airtable_rashidazarang` | airtable-mcp | AIRTABLE_TOKEN, AIRTABLE_BASE_ID | https://github.com/rashidazarang/airtable-mcp |
| [ ] | data | `aiven` | Aiven | AIVEN_TOKEN | https://github.com/Aiven-Open/mcp-aiven |
| [ ] | data | `alchemy` | mcp-alchemy | DB_URL | https://github.com/runekaagaard/mcp-alchemy |
| [ ] | data | `bigquery` | mcp-bigquery-server | PROJECT_ID | https://github.com/ergut/mcp-bigquery-server |
| [ ] | data | `bigquery_lucashild` | BigQuery (by LucasHild) | PROJECT, LOCATION | https://github.com/LucasHild/mcp-server-bigquery |
| [ ] | data | `box` | box-mcp-server | BOX_JWT_BASE64 | https://github.com/hmk/box-mcp-server |
| [ ] | data | `dchub` | DC Hub | DCHUB_API_KEY | https://github.com/azmartone67/dchub-mcp-server |
| [ ] | data | `duckdb` | mcp-server-duckdb | DB_PATH | https://github.com/ktanaka101/mcp-server-duckdb |
| [ ] | data | `elasticsearch` | elasticsearch-mcp-server | ELASTICSEARCH_CLUSTERS | https://github.com/cr7258/elasticsearch-mcp-server |
| [ ] | data | `excel_haris_musa` | Excel (by haris-musa) | ALLOW_DIR | https://github.com/haris-musa/excel-mcp-server |
| [ ] | data | `file_merger` | mcp-file-merger | PATH | https://github.com/exoticknight/mcp-file-merger |
| [ ] | data | `firebase` | firebase-mcp | SERVICE_ACCOUNT_KEY_PATH, FIREBASE_STORAGE_BUCKET | https://github.com/gannonh/firebase-mcp |
| [ ] | data | `gangtise_mcp` | Gangtise投研 | GTS_ACCESS_KEY, GTS_SECRET_KEY | https://open-platform.gangtise.com/ |
| [ ] | data | `gildata` | 恒生聚源 MCP | GILDATA_TOKEN | https://www.feishu.cn/docx/MeCmd4q0Yo7nmkx9D8IcMYbknob |
| [ ] | data | `google_sheets` | mcp-google-sheets | SERVICE_ACCOUNT_PATH | https://github.com/xing5/mcp-google-sheets |
| [ ] | data | `hushvert` | mcp | HUSHVERT_API_KEY | https://github.com/hushvert/mcp |
| [ ] | data | `influxdb` | influxdb-mcp-server | INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET | https://github.com/idoru/influxdb-mcp-server |
| [ ] | data | `mongo_quantgeekdev` | mongo-mcp | PATH | https://github.com/QuantGeekDev/mongo-mcp |
| [ ] | data | `mongodb_lens` | mongodb-lens | PATH | https://github.com/furey/mongodb-lens |
| [ ] | data | `mysql` | mysql_mcp_server | MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE | https://github.com/designcomputer/mysql_mcp_server |
| [ ] | data | `mysql_benborla29` | MySQL | MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, PATH, NODE_PATH | https://www.npmjs.com/package/@benborla29/mcp-server-mysql |
| [ ] | data | `mysql_f4ww4z` | mcp-mysql-server | PATH | https://github.com/f4ww4z/mcp-mysql-server |
| [ ] | data | `mysql_legacy` | mysql-legacy-mcp | MYSQL_LEGACY_PASSWORD | https://github.com/Rufflet/mysql-legacy-mcp |
| [ ] | data | `opendal` | mcp-server-opendal | YOUR_ENV_VAR | https://github.com/Xuanwo/mcp-server-opendal |
| [ ] | data | `platform` | mcp-flowcore-platform | USERNAME, PAT | https://github.com/flowcore-io/mcp-flowcore-platform |
| [ ] | data | `qdrant` | Qdrant | QDRANT_URL, QDRANT_API_KEY, COLLECTION_NAME | https://github.com/qdrant/mcp-server-qdrant/ |
| [ ] | data | `redis` | mcp-redis | URL | https://github.com/redis/mcp-redis |
| [ ] | data | `snowflake` | mcp-snowflake-server | ACCOUNT, WAREHOUSE, USER, PASSWORD, ROLE, DATABASE, SCHEMA | https://github.com/isaacwasserman/mcp-snowflake-server |
| [ ] | data | `sq_company_dynamic` | 上奇产业通-企业动态追踪 | API_KEY | https://ai.chanyedata.com/ai-quantitative/#/workspace/developer |
| [ ] | data | `supabase_2` | Supabase | SUPABASE_ACCESS_TOKEN | https://www.npmjs.com/package/@supabase/mcp-server-supabase |
| [ ] | data | `timeplus` | mcp-timeplus | TIMEPLUS_HOST, TIMEPLUS_PORT, TIMEPLUS_USER, TIMEPLUS_PASSWORD | https://github.com/jovezhong/mcp-timeplus |
| [ ] | data | `tinybird` | Tinybird | TB_API_URL, TB_ADMIN_TOKEN | https://github.com/tinybirdco/mcp-tinybird |
| [ ] | data | `vikingdb` | vikingdb-mcp-server | VIKINGDB_HOST, VIKINGDB_REGION, VIKINGDB_AK, VIKINGDB_SK, COLLECTION_NAME, INDEX_NAME | https://github.com/KashiwaByte/vikingdb-mcp-server |
| [ ] | data | `yingmi_mcp` | 盈米MCP | YINGMI_API_KEY | https://qieman.com/mcp |
| [ ] | dev | `apifox` | Apifox | PROJECT_ID, APIFOX_ACCESS_TOKEN | https://www.npmjs.com/package/apifox-mcp-server |
| [ ] | dev | `azure_devops` | mcp-server-azure-devops | AZURE_DEVOPS_ORG_URL, AZURE_DEVOPS_DEFAULT_PROJECT | https://github.com/Tiberriver256/mcp-server-azure-devops |
| [ ] | dev | `bugsnag` | bugsnag-mcp | BUGSNAG_API_KEY | https://github.com/tgeselle/bugsnag-mcp |
| [ ] | dev | `cli` | cli-mcp-server | ALLOWED_DIR | https://github.com/MladenSU/cli-mcp-server |
| [ ] | dev | `coding_tools` | Coding Tools MCP | WORKSPACE | https://github.com/xyTom/coding-tools-mcp |
| [ ] | dev | `erius_phone` | ERIUS PHONE MCP | ERIUS_PHONE_API_KEY, ERIUS_PHONE_DEFAULT_DEVICE | https://github.com/Protremix/erius-phone-mcp |
| [ ] | dev | `ghcard` | ghcard | GHCARD_API_KEY | https://github.com/ghcardhq/ghcard |
| [ ] | dev | `gitee_oschina` | Gitee | GITEE_ACCESS_TOKEN | https://github.com/oschina/mcp-gitee |
| [ ] | dev | `github_enterprise` | github-enterprise-mcp | TOKEN, GITHUB_ENTERPRISE_URL | https://github.com/ddukbg/github-enterprise-mcp |
| [ ] | dev | `gitlab` | GitLab | GITLAB_PERSONAL_ACCESS_TOKEN, GITLAB_API_URL | https://www.npmjs.com/package/@zereight/mcp-gitlab |
| [ ] | dev | `mem0` | mem0-mcp | MEM0_API_KEY, MEM0_DEFAULT_USER_ID | https://github.com/mem0ai/mem0-mcp |
| [ ] | dev | `probe_kit` | mcp-probe-kit | MEMORY_QDRANT_API_KEY, MEMORY_EMBEDDING_API_KEY | https://github.com/mybolide/mcp-probe-kit |
| [ ] | dev | `reqlan` | reqlan | REQLAN_WORKSPACE | https://github.com/littletuna4/reqlan/tree/main/packages/mcp |
| [ ] | dev | `restcsv` | restcsv-mcp-server | RESTCSV_API_KEY | https://github.com/JordanDalton/RestCsvMcpServer |
| [ ] | dev | `semgrep` | Semgrep | SEMGREP_APP_TOKEN | https://github.com/semgrep/mcp |
| [ ] | dev | `shadcn_ui` | shadcn-ui-mcp-server | GITHUB_API_KEY | https://github.com/Jpisnice/shadcn-ui-mcp-server |
| [ ] | dev | `typescribe` | mcp-typescribe | ARG_2 | https://github.com/yWorks/mcp-typescribe |
| [ ] | dev | `yepcode` | mcp-server-js | YEPCODE_API_TOKEN | https://github.com/yepcode/mcp-server-js |
| [ ] | infra | `adls2` | adls-mcp-server | AZURE_STORAGE_ACCOUNT_NAME | https://github.com/erikhoward/adls-mcp-server |
| [ ] | infra | `alibabacloud_dataworks` | Alibaba Cloud DataWorks | REGION, ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET, TOOL_CATEGORIES, TOOL_NAMES | https://github.com/aliyun/alibabacloud-dataworks-mcp-server |
| [ ] | infra | `cloudflare` | Cloudflare | CLOUDFLARE_API_TOKEN | https://www.npmjs.com/package/@cloudflare/mcp-server-cloudflare |
| [ ] | infra | `cos` | 腾讯云COS | Region, Bucket, SecretId, SecretKey, DatasetName | https://www.npmjs.com/package/cos-mcp |
| [ ] | infra | `edgeone_pages` | Tencent EdgeOne Pages | EDGEONE_PAGES_API_TOKEN, EDGEONE_PAGES_PROJECT_NAME | https://www.npmjs.com/package/edgeone-pages-mcp |
| [ ] | infra | `ipfs` | mcp-ipfs | W3_LOGIN_EMAIL | https://github.com/alexbakers/mcp-ipfs |
| [ ] | infra | `shodan` | mcp-shodan | SHODAN_API_KEY | https://github.com/BurtTheCoder/mcp-shodan |
| [ ] | infra | `threatcluster` | Threat-Intelligence-MCP | THREATCLUSTER_API_KEY | https://github.com/Jam0k/Threat-Intelligence-MCP |
| [ ] | infra | `virustotal` | mcp-virustotal | VIRUSTOTAL_API_KEY | https://github.com/BurtTheCoder/mcp-virustotal |
| [ ] | media | `amazon_bedrock` | Amazon Bedrock Nova Canvas | AWS_PROFILE, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY | https://github.com/zxkane/mcp-server-amazon-bedrock |
| [ ] | media | `dinox` | DINO-X-MCP | DINOX_API_KEY, IMAGE_STORAGE_DIRECTORY | https://github.com/IDEA-Research/DINO-X-MCP |
| [ ] | media | `elevenlabs` | ElevenLabs | ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID | https://github.com/mamertofabian/elevenlabs-mcp-server |
| [ ] | media | `elevenlabs_2` | ElevenLabs (官方) | ELEVENLABS_API_KEY | https://github.com/elevenlabs/elevenlabs-mcp |
| [ ] | media | `figma_developer` | Figma-Context-MCP | FIGMA_API_KEY | https://github.com/GLips/Figma-Context-MCP |
| [ ] | media | `image_compression` | mcp-image-compression | IMAGE_COMPRESSION_DOWNLOAD_DIR | https://github.com/InhiblabCore/mcp-image-compression |
| [ ] | media | `image_gen` | Image Generation | REPLICATE_API_TOKEN | https://github.com/GongRzhe/Image-Generation-MCP-Server |
| [ ] | media | `minimax` | MiniMax (官方) | MINIMAX_API_KEY | https://github.com/MiniMax-AI/MiniMax-MCP |
| [ ] | media | `pixelbolt` | Pixelbolt | OUT | https://github.com/skulitom/Pixelbolt |
| [ ] | media | `replicate_flux` | replicate-flux-mcp | REPLICATE_API_TOKEN | https://github.com/awkoy/replicate-flux-mcp |
| [ ] | media | `sightradar` | SightRadar Face Recognition API MCP | SIGHTRADAR_API_KEY | https://github.com/sightradar-hq/sightradar-mcp |
| [ ] | media | `speakai` | Speak AI | SPEAK_API_KEY | https://github.com/speakai/speakai-mcp |
| [ ] | media | `transcriptdock` | Transcript Dock | TRANSCRIPTDOCK_API_KEY | https://github.com/TranscriptDock/transcriptdock-mcp |
| [ ] | media | `transcriptfetch` | mcp-server | TRANSCRIPTFETCH_API_KEY | https://github.com/TranscriptFetch/mcp-server |
| [ ] | media | `video_editor` | video-editing-mcp | ARG_1 | https://github.com/burningion/video-editing-mcp |
| [ ] | media | `wiro` | Wiro AI | WIRO_API_KEY, WIRO_API_SECRET | https://github.com/wiroai/Wiro-MCP |
| [ ] | media | `zubeid_youtube` | YouTube | YOUTUBE_API_KEY, YOUTUBE_API_KEY2, YOUTUBE_API_KEY3 | https://github.com/ZubeidHendricks/youtube-mcp-server |
| [ ] | misc | `agentrpc` | AgentRPC | AGENTRPC_API_SECRET | https://github.com/agentrpc/agentrpc |
| [ ] | misc | `amap_maps` | 高德地图 | AMAP_MAPS_API_KEY | https://www.npmjs.com/package/@amap/amap-maps-mcp-server |
| [ ] | misc | `any_chat_completions` | any-chat-completions-mcp | AI_CHAT_KEY | https://github.com/pyroprompts/any-chat-completions-mcp |
| [ ] | misc | `apifox_wangmhaha` | Apifox | APIFOX_API_KEY, PROJECT_ID | https://www.npmjs.com/package/@wangmhaha/apifox-mcp-server |
| [ ] | misc | `baidu_map` | 百度地图 | BAIDU_MAP_API_KEY | https://www.npmjs.com/package/@baidumap/mcp-server-baidu-map |
| [ ] | misc | `balldontlie` | balldontlie-mcp | BALLDONTLIE_API_KEY | https://github.com/mikechao/balldontlie-mcp |
| [ ] | misc | `footballcharts` | footballcharts-mcp | FC_API_KEY | https://github.com/ddevetak/footballcharts-mcp |
| [ ] | misc | `giphy` | mcp-server-giphy | GIPHY_API_KEY | https://github.com/magarcia/mcp-server-giphy |
| [ ] | misc | `graphql_schema` | GraphQL Schema | PATH | https://github.com/hannesj/mcp-graphql-schema |
| [ ] | misc | `ip2location_io` | mcp-ip2location-io | IP2LOCATION_API_KEY | https://github.com/ip2location/mcp-ip2location-io |
| [ ] | misc | `leetcode` | LeetCode | LEETCODE_SESSION | https://www.npmjs.com/package/@jinzcdev/leetcode-mcp-server |
| [ ] | misc | `livetennisapi` | livetennisapi-mcp | LIVETENNISAPI_KEY | https://github.com/livetennisapi/livetennisapi-mcp |
| [ ] | misc | `multiverse` | mcp-server-multiverse | PATH | https://github.com/lamemind/mcp-server-multiverse |
| [ ] | misc | `opanel` | opanel-mcp | SERVER, TOKEN | https://github.com/opanel-mc/opanel-mcp |
| [ ] | misc | `openai` | mcp-openai | OPENAI_API_KEY | https://github.com/mzxrai/mcp-openai |
| [ ] | misc | `openapi_schema` | OpenAPI Schema | PATH | https://github.com/hannesj/mcp-openapi-schema |
| [ ] | misc | `oura` | oura-mcp-server | OURA_API_TOKEN | https://github.com/tomekkorbak/oura-mcp-server |
| [ ] | misc | `parlayapi` | ParlayAPI | PARLAYAPI_KEY | https://github.com/JacobiusMakes/parlay-api-mcp |
| [ ] | misc | `pluggedin_proxy` | pluggedin-mcp-proxy | PLUGGEDIN_API_KEY | https://github.com/VeriTeknik/pluggedin-mcp-proxy |
| [ ] | misc | `studio_sidecar` | studio-sidecar-mcp | ROBLOX_API_KEY, ROBLOX_CREATOR_USER_ID, ROBLOX_UPLOAD_ROOT, ROBLOX_PUBLISH_PLACE_IDS | https://github.com/gjlmotea/studio-sidecar-mcp |
| [ ] | misc | `task_master_ai` | 任务大师 | ANTHROPIC_API_KEY, PERPLEXITY_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY, XAI_API_KEY, AZURE_OPENAI_API_KEY, OLLAMA_API_KEY | https://www.npmjs.com/package/task-master-ai |
| [ ] | misc | `unichat` | unichat-mcp-server | UNICHAT_API_KEY | https://github.com/amidabuddha/unichat-mcp-server |
| [ ] | misc | `wolfram_alpha` | MCP-wolfram-alpha | WOLFRAM_API_KEY | https://github.com/SecretiveShell/MCP-wolfram-alpha |
| [ ] | office | `asana` | mcp-server-asana | ASANA_ACCESS_TOKEN | https://github.com/roychri/mcp-server-asana |
| [ ] | office | `atlassian` | mcp-atlassian | JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN | https://github.com/sooperset/mcp-atlassian |
| [ ] | office | `attio` | attio-mcp-server | ATTIO_API_KEY | https://github.com/hmk/attio-mcp-server |
| [ ] | office | `dsh_novel_writer` | dsh-novel-writer | ROOT | https://github.com/siweina/dsh-novel-writer |
| [ ] | office | `evc_team_relay` | evc-team-relay-mcp | RELAY_CP_URL, RELAY_AGENT_KEY | https://github.com/entire-vc/evc-team-relay-mcp |
| [ ] | office | `feishu_2` | 飞书 | FEISHU_APP_ID, FEISHU_APP_SECRET | https://www.npmjs.com/package/feishu-mcp |
| [ ] | office | `flomo` | Flomo | FLOMO_API_URL | https://www.npmjs.com/package/mcp-server-flomo |
| [ ] | office | `hackmd` | hackmd-mcp | HACKMD_API_TOKEN | https://github.com/yuna0x0/hackmd-mcp |
| [ ] | office | `home_assistant` | mcp-server-home-assistant | HOME_ASSISTANT_WEB_SOCKET_URL, HOME_ASSISTANT_API_TOKEN | https://github.com/allenporter/mcp-server-home-assistant |
| [ ] | office | `linear_jerhadf` | Linear (by jerhadf) | LINEAR_API_KEY | https://github.com/jerhadf/linear-mcp-server |
| [ ] | office | `miro_k_jarzyna` | mcp-miro | MIRO_ACCESS_TOKEN | https://github.com/k-jarzyna/mcp-miro |
| [ ] | office | `notion_notionhq` | Notion | OPENAPI_MCP_HEADERS | https://www.npmjs.com/package/@notionhq/notion-mcp-server |
| [ ] | office | `notion_suekou` | mcp-notion-server | NOTION_API_TOKEN | https://github.com/suekou/mcp-notion-server |
| [ ] | office | `obsidian` | mcp-obsidian | OBSIDIAN_API_KEY, OBSIDIAN_HOST, OBSIDIAN_PORT | https://github.com/MarkusPfundstein/mcp-obsidian |
| [ ] | office | `taskade` | Taskade MCP | TASKADE_API_KEY | https://github.com/taskade/mcp |
| [ ] | office | `todoist` | Todoist | TODOIST_API_TOKEN | https://github.com/abhiz123/todoist-mcp-server |
| [ ] | office | `yuque` | 语雀 | YUQUE_PERSONAL_TOKEN | https://github.com/yuque/yuque-mcp-server |
| [ ] | social | `jobson_xhs` | xhs-mcp | XHS_COOKIE | https://github.com/jobsonlook/xhs-mcp |
| [ ] | web | `brave_search` | Brave Search (官方) | BRAVE_API_KEY | https://github.com/brave/brave-search-mcp-server |
| [ ] | web | `buywhere` | BuyWhere | BUYWHERE_API_KEY | https://github.com/BuyWhere/buywhere-mcp |
| [ ] | web | `desearch` | Desearch | DESEARCH_API_KEY | https://github.com/Desearch-ai/mcp-desearch |
| [ ] | web | `dumplingai` | mcp-server-dumplingai | DUMPLING_API_KEY | https://github.com/Dumpling-AI/mcp-server-dumplingai |
| [ ] | web | `exa_2` | Exa搜索 | EXA_API_KEY | https://www.npmjs.com/package/exa-mcp-server |
| [ ] | web | `google_news` | google-news-mcp-server | SERP_API_KEY | https://github.com/ChanMeng666/server-google-news |
| [ ] | web | `google_search` | Google Custom Search | GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID | https://github.com/adenot/mcp-google-search |
| [ ] | web | `hyperbrowser` | Hyperbrowser | HYPERBROWSER_API_KEY | https://github.com/hyperbrowserai/mcp |
| [ ] | web | `omophub` | OMOPHub | OMOPHUB_API_KEY | https://github.com/OMOPHub/omophub-mcp |
| [ ] | web | `openai_websearch` | openai-websearch-mcp | OPENAI_API_KEY | https://github.com/ConechoAI/openai-websearch-mcp |
| [ ] | web | `oxylabs` | Oxylabs | OXYLABS_API_TOKEN, OXYLABS_AI_STUDIO_API_KEY | https://github.com/oxylabs/oxylabs-mcp |
| [ ] | web | `perplexity_ai` | Perplexity | PERPLEXITY_API_KEY | https://github.com/ppl-ai/modelcontextprotocol |
| [ ] | web | `rag_web_browser` | RAG Web Browser | APIFY_TOKEN | https://github.com/apify/mcp-server-rag-web-browser |
| [ ] | web | `scrapely` | scrapely-mcp | SCRAPELY_TOKEN | https://github.com/scrapely-app/scrapely-mcp |
| [ ] | web | `search1api` | Search1API | SEARCH1API_KEY | https://github.com/fatwang2/search1api-mcp |
| [ ] | web | `searxng` | MCP-SearXNG | SEARXNG_URL | https://github.com/ihor-sokoliuk/mcp-searxng |
| [ ] | web | `secret_design` | Secret MCP | DESIGN_INDEX_OUTPUT_DIR, SECRET_MCP_WEB_ORIGIN | https://github.com/yyeongjin/secret_mcp |
| [ ] | web | `snaprender` | SnapRender | SNAPRENDER_API_KEY | https://github.com/User0856/snaprender-integrations |
| [ ] | web | `tavily_mcptools` | mcp-tavily | TAVILY_API_KEY | https://github.com/kshern/mcp-tavily.git |
| [ ] | web | `trieve` | trieve | TRIEVE_API_KEY | https://github.com/devflowinc/trieve/tree/main/clients/mcp-server |
| [ ] | web | `unblockingapi` | mcp | UNBLOCKINGAPI_KEY | https://github.com/unblockingapi/mcp |
| [ ] | web | `vectorize` | vectorize-mcp-server | VECTORIZE_ORG_ID, VECTORIZE_TOKEN, VECTORIZE_PIPELINE_ID | https://github.com/vectorize-io/vectorize-mcp-server |
| [ ] | web | `zoomeye` | mcp_zoomeye | ZOOMEYE_API_KEY | https://github.com/zoomeye-ai/mcp_zoomeye |
