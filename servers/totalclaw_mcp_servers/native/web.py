"""网页抓取 MCP 服务器 —— 抓取 URL 并抽取正文纯文本。

原生实现而非 pack：base_url 由调用方给（pack 的 base_url 是固定的），
还要做 HTML 正文抽取、字符集嗅探与 SSRF 防护，声明式表达不了。

零凭据、零重依赖：只用标准库的 HTMLParser 做抽取。
"""
from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

MAX_CHARS = 16000
HARD_MAX_CHARS = 60000
MAX_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 20.0
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas", "iframe"}
_BLOCK_TAGS = {"p", "div", "section", "article", "br", "li", "tr", "h1", "h2", "h3",
               "h4", "h5", "h6", "blockquote", "pre", "td", "th", "header", "footer"}


class WebError(Exception):
    """面向用户的错误。"""

    clean = True


# ── SSRF 防护 ────────────────────────────────────────────────────────────

def _allow_private() -> bool:
    """代理环境逃生阀。

    Clash / Surge 这类工具会把公网域名解析到 fake-IP 段（198.18.0.0/15 等保留段），
    严格校验会把正常网站全拦掉。设 TOTALCLAW_MCP_WEB_ALLOW_PRIVATE=1 关闭地址校验
    —— 仅在你信任本机网络环境时使用。
    """
    import os

    return os.environ.get("TOTALCLAW_MCP_WEB_ALLOW_PRIVATE", "").lower() in ("1", "true", "yes", "on")


def _check_url(url: str) -> str:
    """只允许 http(s)，且默认拒绝解析到内网/回环/链路本地地址的目标。"""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise WebError(f"只支持 http/https，收到 {p.scheme or '空'}://")
    if not p.hostname:
        raise WebError("URL 里没有主机名")
    if _allow_private():
        return url
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror as e:
        raise WebError(f"域名解析失败：{p.hostname}（{e.strerror or e}）") from e
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise WebError(
                f"拒绝访问内网地址：{p.hostname} → {addr}。"
                "若本机用了 Clash / Surge 这类代理（会把公网域名解析到保留段），"
                "设 TOTALCLAW_MCP_WEB_ALLOW_PRIVATE=1 可跳过该校验。"
            )
    return url


# ── HTML 抽取 ────────────────────────────────────────────────────────────

class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self.links: list[tuple[str, str]] = []
        self._skip = 0
        self._in_title = False
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._link_text = []
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a":
            text = "".join(self._link_text).strip()
            if self._href and text:
                self.links.append((text, self._href))
            self._href = None
            self._link_text = []
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title += data
            return
        self.parts.append(data)
        if self._href is not None:
            self._link_text.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t\xa0]+", " ", raw)
        raw = re.sub(r"\n[ \t]*", "\n", raw)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def _decode(content: bytes, ctype: str) -> str:
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    candidates = [m.group(1)] if m else []
    head = content[:2048].decode("ascii", "ignore")
    m2 = re.search(r'charset=["\']?([\w-]+)', head, re.I)
    if m2:
        candidates.append(m2.group(1))
    candidates += ["utf-8", "gb18030", "big5", "latin-1"]
    for cs in candidates:
        try:
            return content.decode(cs)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", "replace")


# ── 工具实现 ─────────────────────────────────────────────────────────────

def fetch_url(*, url: str, max_chars: int = MAX_CHARS,
              include_links: bool = False, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    import httpx

    _check_url(url)
    limit = max(200, min(int(max_chars or MAX_CHARS), HARD_MAX_CHARS))
    try:
        with httpx.Client(follow_redirects=True, timeout=float(timeout or DEFAULT_TIMEOUT),
                          max_redirects=5) as c:
            resp = c.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; totalclaw-mcp/0.1)",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            })
    except httpx.TimeoutException:
        return {"success": False, "error": f"抓取超时（{timeout}s）：{url}"}
    except httpx.HTTPError as e:
        return {"success": False, "error": f"抓取失败：{type(e).__name__}: {e}"}

    if resp.status_code >= 400:
        return {"success": False, "error": f"目标返回 HTTP {resp.status_code}：{url}",
                "status": resp.status_code}

    content = resp.content[:MAX_BYTES]
    ctype = (resp.headers.get("content-type") or "").lower()
    out: dict[str, Any] = {"url": str(resp.url), "status": resp.status_code,
                           "content_type": ctype.split(";")[0] or "unknown"}

    if "json" in ctype:
        import json

        try:
            out["json"] = json.loads(_decode(content, ctype))
            return {"success": True, "data": out}
        except (ValueError, json.JSONDecodeError):
            pass

    if "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        out["note"] = "非文本内容，只返回元信息"
        out["bytes"] = len(resp.content)
        return {"success": True, "data": out}

    text = _decode(content, ctype)
    if "html" in ctype or text.lstrip()[:5].lower().startswith("<!doc") or "<html" in text[:500].lower():
        ex = _Extractor()
        try:
            ex.feed(text)
        except Exception:  # noqa: BLE001 - 畸形 HTML 不该让整次调用失败
            pass
        out["title"] = ex.title.strip()
        body = ex.text()
        if include_links:
            base = str(resp.url)
            out["links"] = [{"text": t[:120], "url": urljoin(base, h)}
                            for t, h in ex.links[:100]]
    else:
        body = text.strip()

    if len(body) > limit:
        out["text"] = body[:limit]
        out["truncated"] = {"returned": limit, "total": len(body)}
    else:
        out["text"] = body
    return {"success": True, "data": out}


def fetch_many(*, urls: list[str], max_chars: int = 4000) -> dict[str, Any]:
    if not urls:
        return {"success": False, "error": "urls 不能为空"}
    if len(urls) > 10:
        return {"success": False, "error": f"一次最多 10 个 URL，收到 {len(urls)} 个"}
    results = []
    for u in urls:
        try:
            r = fetch_url(url=u, max_chars=max_chars)
        except WebError as e:
            r = {"success": False, "error": str(e)}
        results.append({"url": u, **({"data": r.get("data")} if r.get("success")
                                     else {"error": r.get("error")})})
    return {"success": True, "data": results}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "fetch_url",
        "description": "抓取一个网页并返回标题与正文纯文本。JSON 接口会直接返回解析后的 JSON；"
                       "非文本内容只返回元信息。拒绝访问内网地址。",
        "read_only": True,
        "handler": fetch_url,
        "schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标网页 URL，必须是 http/https"},
                "max_chars": {"type": "integer",
                              "description": "正文最大返回字符数，默认 16000，上限 60000"},
                "include_links": {"type": "boolean",
                                  "description": "是否同时返回页面里的链接（最多 100 条）"},
                "timeout": {"type": "number", "description": "超时秒数，默认 20"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "fetch_many",
        "description": "一次抓取多个网页（最多 10 个），每个只返回较短的正文摘要，"
                       "适合快速比较多个来源。单个失败不影响其余。",
        "read_only": True,
        "handler": fetch_many,
        "schema": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"},
                         "description": "URL 列表，最多 10 个"},
                "max_chars": {"type": "integer", "description": "每个页面的正文上限，默认 4000"},
            },
            "required": ["urls"],
        },
    },
]

SERVER_NAME = "web"
DISPLAY_NAME = "网页抓取"
DESCRIPTION = "抓取网页并抽取正文纯文本，支持批量抓取与 JSON 接口，零凭据。"
DESCRIPTION_EN = 'Fetch web pages and extract readable text; supports batch fetch and JSON endpoints. No credentials.'
REQUIRED_ENV: list[str] = []
OPTIONAL_ENV: list[str] = ["TOTALCLAW_MCP_WEB_ALLOW_PRIVATE"]
