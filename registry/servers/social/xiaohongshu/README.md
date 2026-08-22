# 小红书

小红书图文/视频发布、关键词搜索、推荐流获取、帖子详情、评论(发表/回复/点赞)、收藏、用户主页、登录状态检查(13 工具)。

## 安装前置

docker pull xpzouying/xiaohongshu-mcp && cd docker && docker compose up -d。首次需 ./xiaohongshu-login-* 扫码登录,登录 cookie 自动持久化。可选 XHS_PROXY 代理。

**鉴权**：首次扫码登录(无 API key);可选 XHS_PROXY 环境变量

来源：https://github.com/xpzouying/xiaohongshu-mcp

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
