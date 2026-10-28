# TopView Canvas 画布 MCP（topview_canvas）

端点 `https://mcp-browser.topview.ai`，浏览器 OAuth（授权服务器 `https://mcp.topview.ai`，scope `mcp:tools`）。
装完运行 `totalclaw mcp login topview_canvas` 授权。Unlimited 套餐不可用。

适用场景：长视频、多镜头、要在画布上排分镜和时间线的工作流。`topview_official` 的
`topview_prepare_canvas_jump` 只把用户带到网页 Canvas，本服务器则让 Agent 直接操作画布。

## 工具清单（据官方开源文档整理，非实测）

来源：[topviewai/plugins](https://github.com/topviewai/plugins)（MIT，`3dafaf9`，2026-09-23）的
`plugins/topview-browser/skills/operate-topview-canvas/references/canvas-mcp-api.md`。
该文档标称 42 个工具，下表列出文档里写明的 40 个。以线上 `tools/list` 为准。

| 分组 | 工具 |
|---|---|
| 画布生命周期 | `list_topview_canvases`、`create_topview_canvas`、`get_topview_canvas_metadata`、`update_topview_canvas_metadata`、`delete_topview_canvas` |
| 打开 / 读取 | `open_topview_canvas`、`open_topview_canvas_workspace`、`get_topview_canvas_web_link`、`get_topview_canvas_state`、`get_topview_canvas_node_details`、`get_topview_canvas_timeline`、`get_topview_canvas_timeline_export`、`download_topview_canvas_nodes` |
| 本地素材上传 | `prepare_topview_canvas_media_upload`（返回签名 URL，PUT 后再建 media 节点） |
| 建节点 | `create_topview_canvas_text_node`、`create_topview_canvas_media_node`、`create_topview_canvas_generation_card`、`create_topview_canvas_scene_node`、`create_topview_canvas_file_node`、`create_topview_canvas_asset_node`、`create_topview_canvas_group_node` |
| 生成（付费） | `get_topview_canvas_generation_capabilities` → `submit_topview_canvas_generation_task` → `refresh_topview_canvas_generation_task` |
| 编辑 / 布局 | `update_topview_canvas_node`、`update_topview_canvas_asset_node`、`update_topview_canvas_scene_node`、`set_topview_canvas_node_parent`、`set_topview_canvas_nodes_state`、`move_topview_canvas_node`、`transform_topview_canvas_nodes`、`duplicate_topview_canvas_nodes`、`arrange_topview_canvas_nodes`、`set_topview_canvas_node_layer`、`group_topview_canvas_nodes`、`ungroup_topview_canvas_nodes`、`normalize_topview_canvas_layout`、`delete_topview_canvas_nodes` |
| 时间线 / 导出 | `edit_topview_canvas_timeline`（目前只支持 `append_clip`）、`submit_topview_canvas_timeline_export` |

官方插件还会调用 `topview_check_plugin_update`、`topview_ack_plugin_update`、`topview_report_skill_feedback`。
这三个是官方插件自己的版本检查和反馈工具，TotalClaw 接入时用不到。

注意：

- `create_topview_canvas_generation_card` 只建草稿卡片，不扣积分。真正扣积分的是 `submit_topview_canvas_generation_task`，调用前需要用户确认。
- `delete_topview_canvas` 要求 `confirmCanvasId` 与 `canvasId` 完全一致。
