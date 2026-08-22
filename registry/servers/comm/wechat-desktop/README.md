# WeChat Desktop (built-in)

桌面微信自控 —— 自动检测 OS(Windows/macOS/Linux)调对应底层:wechat_capabilities/list_unread/open_chat/read_chat/screenshot_chat/send_message。分层读取:native_text(AX/UIA 免模型)→ ocr → clipboard → screenshot(交 agent 视觉)。发送用确定性几何。

## 安装前置

需本机微信客户端在跑并已登录;macOS 需授予辅助功能+屏幕录制权限。Windows(UIA)/Linux 为盲写路径待真机验证。

**鉴权**：无 API key(扫码登录本机微信);⚠️ 个人号自动化违反微信 ToS,灰区风险自担,勿用于群发/营销/代运营。

来源：totalclaw_core/tools/wechat_py_mcp.py(本仓自建 clean-room)

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
