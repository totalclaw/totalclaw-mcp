# 抖音 / 小红书

抖音+小红书内容提取/去水印/语音转文字:get_douyin_download_link / extract_douyin_text / parse_douyin_video_info / get_xiaohongshu_content / extract_xiaohongshu_text / extract_xiaohongshu_video_text / get_xiaohongshu_images / remove_xiaohongshu_video_watermark(8 工具)。

## 安装前置

pip install douyin-mcp-server。生成 config.json:{"api_key": "sk-...","model": "paraformer-v2","language_hints": ["zh","en"],"temp_dir": "temp"}。

**鉴权**：阿里云百炼(DashScope)API key — paraformer-v2 语音模型

来源：https://github.com/AshinH/dy-xhs-mcp-server

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
