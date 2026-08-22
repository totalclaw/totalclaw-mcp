# Playwright (built-in Python)

纯 Python Playwright MCP —— 浏览器自动化首选(零 Node)。navigate/snapshot/click/type/eval/screenshot/back。BROWSER_CDP_URL 设了则接管用户已开 Chrome,否则自启 Chromium。

## 安装前置

依赖 playwright Python 库(已在 requirements)+ 浏览器二进制:首次 `python -m playwright install chromium`。

**鉴权**：无(本地浏览器)

来源：totalclaw_core/tools/playwright_py_mcp.py(本仓自建)

> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。
