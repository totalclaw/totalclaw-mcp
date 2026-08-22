# Chrome DevTools

谷歌浏览器(Chrome)DevTools 控制 — 自动化导航/点击/填表、性能 trace + Lighthouse 审计、网络请求观察、控制台日志读取、JS 执行、heap snapshot、屏幕截图、扩展安装。支持 --headless / --isolated / --browser-url 接已有 Chrome。

## 安装前置

需本机有 Chrome / Edge / Chromium。首次 npx 自动拉镜像。也可加 args ``["-y", "chrome-devtools-mcp@latest", "--headless", "--isolated"]`` 跑无头隔离模式。

**鉴权**：无(本地浏览器自动化)

来源：https://github.com/ChromeDevTools/chrome-devtools-mcp

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
