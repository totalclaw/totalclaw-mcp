# TopView 官方 MCP（topview_official）

端点 `https://mcp.topview.ai/mcp`，浏览器 OAuth（DCR + PKCE，scope `mcp:tools`）。
装完运行 `totalclaw mcp login topview_official` 授权。Unlimited 套餐不可用。

## 工具清单（据官方开源文档整理，非实测）

目前没有拿到 OAuth 授权，所以没有实际跑过 `tools/list`。下表依据以下官方开源仓库整理：

- [topviewai/skill](https://github.com/topviewai/skill)（Apache-2.0，`5e0fa64`，2026-07-23）：
  `topview-generate/SKILL.md`、`*/references/tool_routing.md`
- [topviewai/plugins](https://github.com/topviewai/plugins)（MIT，`3dafaf9`，2026-09-23）

以线上 `tools/list` 为准，CI 探测（`scripts/probe_server.py`）成功后会生成 `tools.json` 覆盖本节内容。
官方文档的调用参数统一包在 `req` 对象里，例如 `topview_get_credit {"req": {}}`。字段以 live schema 为准。

### 顶层工具（`tools/list` 直接可见）

| 分组 | 工具 |
|---|---|
| 生成配置 | `topview_get_generation_config`（模型与必填字段，生成前先查） |
| 图片 | `topview_generate_image`（text_to_image / image_edit）、`topview_remove_background` |
| 视频 | `topview_generate_video`（text_to_video / image_to_video / omni_reference，≤15s）、`topview_prepare_canvas_jump`（>15s 或多镜头交给 Canvas） |
| 照片数字人 | `topview_avatar_video`（只吃人像照片 + 文本/音频）、`topview_list_captions` |
| 商品模特图 | `topview_list_product_avatar_categories`、`topview_list_product_avatars`、`topview_product_avatar` |
| 语音 / 音乐 | `topview_list_voices`、`topview_generate_voice`、`topview_clone_voice`、`topview_generate_audio`、`topview_generate_music` |
| 任务 | `topview_query_task` |
| 看板 | `topview_list_boards`、`topview_create_board`、`topview_list_board_tasks`、`topview_get_board_task` |
| 积分 | `topview_get_credit`、`topview_list_credit_logs` |
| 上传 | `ta_upload_credential` → PUT 到返回的 URL → `ta_upload_check_file` |
| 电商数据入口 | `use_amazon_data`、`use_tiktok_data`、`use_shopee_data`、`use_youtube_kol` |
| 延迟工具元调用 | `get_tool_schema`、`call_tool` |

### 电商数据（延迟工具，经 `call_tool` 调用）

这些工具不出现在 `tools/list` 里。调用前先用 `get_tool_schema {name, domain}` 取 schema，
再调 `call_tool {name, domain, arguments}`。

| domain | 文档中出现的工具名数 | 例子 |
|---|---|---|
| `amazon` | 约 40 | `market_research`、`product_research`、`keyword_research`、`asin_sales_trend`、`aba_research_weekly` |
| `shopee` | 约 50 | 市场 / 商品 / 店铺 / 品牌 / 关键词分析 |
| `tiktok` | 约 10 | TikTok Shop 商品与达人数据 |
| `youtube_kol` | 约 20 | `youtube_kol_*` 达人检索与分析 |

## 和自研 `topview`（API Key 版）的分工

官方文档里没有下面两项能力，所以自研 `topview` 保留了它们：

- 商品链接一键出带货视频（m2v）：自研版的 `create_marketing_video`。官方只在积分流水类型里出现了 `m2v`。
- 公模数字人口播（`aiavatar` 公共形象库）：自研版的 `list_avatars` 和 `create_avatar_video`。
  官方的 `topview_avatar_video` 只能用照片驱动。

其余生成能力（生图、生视频、配音、克隆音色、抠图、商品模特图）和电商数据都走官方 MCP。
需要无人值守的生图、生视频，用自研 `topview` 的 `router_*` 工具，走新版 API Router，
只要一个 Platform Key。

同一账号还有 Canvas 画布 MCP，见 `topview_canvas`。
