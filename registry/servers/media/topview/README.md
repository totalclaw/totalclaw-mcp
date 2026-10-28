# TopView AI 营销视频

用 TopView 把商品链接一键做成带货短视频，并支持数字人口播、配音、图生视频（API Key 鉴权）。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 10 个工具（只读 5 / 写入 5）。

## 工具

- `get_credit`（只读）— 查询 TopView 账户剩余积分。生成任务前可先查，避免积分不足（code 4100）。
- `list_avatars`（只读）— 列出可用的数字人（公模或自己的私模），返回 aiavatarId、名称、性别、封面、预览视频与默认音色 voiceoverIdDefault。用于 create_marketing_video / create_avatar_video 的 avatar_id。
- `list_voices`（只读）— 列出可用音色，返回 voiceId、名称、擅长语言、口音、性别、年龄、风格与试听地址。
- `list_captions`（只读）— 列出可用的字幕样式，返回 captionId 与预览图。不传 caption_id 时 TopView 随机选一个。
- `upload_file`（**写入**）— 把素材上传到 TopView，返回 fileId 供生成工具使用。三种来源三选一：path（本机文件）、url（公网直链，拒绝内网地址）、base64_data（需同时给 format）。支持 mp4/mov/png/jpg/jpeg/bmp/webp/mp3/wav/m4a，单个不超过 200 MB。
- `create_marketing_video`（**写入**）— 【核心】商品链接一键出带货短视频：TopView 自动解析商品、写脚本、选数字人与配音、剪辑成片。也可不给链接，改用 file_ids（上传的商品图/视频）+ 商品名与描述。custom_script 给了就按你的脚本念（适合先让 LLM 写好文案）。这会消耗 TopView 积分。返回任务状态与成片 videoUrl。
- `create_avatar_video`（**写入**）— 数字人口播：让数字人念一段文本（或对上一段音频的口型）。数字人来源三选一：avatar_id（公模/私模）、image_file_id（一张人像图）、video_file_id（一段人像视频）。这会消耗 TopView 积分。返回成片 videoUrl。
- `create_speech`（**写入**）— 文本转语音，返回音频地址。这会消耗 TopView 积分。
- `create_image_to_video`（**写入**）— 图生视频：把一张商品图/场景图做成 5 或 10 秒的动态视频。这会消耗 TopView 积分。
- `query_task`（只读）— 查询生成任务的进度与结果。state=done 时 urls 里是成片地址；state=running 请稍后再查，不要重复提交任务。

## 安装

```bash
totalclaw mcp install topview
```

## 需要的凭据

- `TOPVIEW_API_KEY`（密钥）
- `TOPVIEW_UID`

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
