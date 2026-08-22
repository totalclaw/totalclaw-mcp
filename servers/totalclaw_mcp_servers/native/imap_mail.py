"""IMAP/SMTP 邮箱 MCP 服务器 —— 覆盖 QQ 邮箱、网易邮箱（163/126/yeah）及任意 IMAP 邮箱。

这是原生实现而非声明式 pack：IMAP 是有状态的长连接协议，还要处理 MIME 解码、
多种字符集、RFC2047 编码头，声明式的 REST 引擎表达不了。

凭据（环境变量）：
    MAIL_IMAP_HOST      IMAP 服务器地址，如 imap.qq.com / imap.163.com
    MAIL_IMAP_PORT      端口，默认 993（SSL）
    MAIL_USERNAME       邮箱地址
    MAIL_PASSWORD       授权码（QQ/163 都不能用登录密码，须在邮箱设置里生成授权码）
    MAIL_SMTP_HOST      发信服务器，可选；不配则不暴露发信工具
    MAIL_SMTP_PORT      发信端口，默认 465（SSL）

已知服务商：
    QQ 邮箱   imap.qq.com:993      smtp.qq.com:465
    163 邮箱  imap.163.com:993     smtp.163.com:465
    126 邮箱  imap.126.com:993     smtp.126.com:465
"""
from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import os
import re
from datetime import datetime, timedelta
from email.message import Message
from typing import Any

MAX_BODY_CHARS = 8000
MAX_FETCH = 50


class MailError(Exception):
    """面向用户的错误：消息已是人话，装配层直接透出，不加类名前缀。"""

    clean = True


# ── 连接 ────────────────────────────────────────────────────────────────

def _require_env() -> tuple[str, int, str, str]:
    host = os.environ.get("MAIL_IMAP_HOST", "").strip()
    user = os.environ.get("MAIL_USERNAME", "").strip()
    pwd = os.environ.get("MAIL_PASSWORD", "")
    missing = [k for k, v in (("MAIL_IMAP_HOST", host), ("MAIL_USERNAME", user),
                              ("MAIL_PASSWORD", pwd)) if not v]
    if missing:
        raise MailError(
            f"缺少凭据环境变量：{', '.join(missing)}。"
            "注意 QQ / 163 邮箱必须使用「授权码」而非登录密码。"
        )
    try:
        port = int(os.environ.get("MAIL_IMAP_PORT") or 993)
    except ValueError:
        port = 993
    return host, port, user, pwd


def _connect() -> imaplib.IMAP4_SSL:
    host, port, user, pwd = _require_env()
    try:
        conn = imaplib.IMAP4_SSL(host, port, timeout=30)
    except OSError as e:
        raise MailError(f"连不上 IMAP 服务器 {host}:{port} —— {e}") from e
    try:
        conn.login(user, pwd)
    except imaplib.IMAP4.error as e:
        raise MailError(
            f"登录失败：{e}。请确认 MAIL_PASSWORD 填的是邮箱授权码，且已开启 IMAP 服务。"
        ) from e
    # 网易系要求声明客户端身份，否则 SELECT 会报 Unsafe Login
    if "163.com" in host or "126.com" in host or "yeah.net" in host:
        try:
            conn._simple_command(
                "ID", '("name" "totalclaw" "version" "1.0" "vendor" "totalclaw")'
            )
        except Exception:  # noqa: BLE001 - ID 不支持时忽略即可
            pass
    return conn


# ── 解码 ────────────────────────────────────────────────────────────────

def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    out = []
    for part, charset in email.header.decode_header(raw):
        if isinstance(part, bytes):
            for cs in (charset, "utf-8", "gb18030", "latin-1"):
                if not cs:
                    continue
                try:
                    out.append(part.decode(cs))
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                out.append(part.decode("utf-8", "replace"))
        else:
            out.append(part)
    return "".join(out).strip()


def _body_text(msg: Message) -> str:
    """优先取 text/plain；没有就把 text/html 粗略转成文本。"""
    html_fallback = ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        if part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001
            continue
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        for cs in (charset, "utf-8", "gb18030", "latin-1"):
            try:
                text = payload.decode(cs)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            text = payload.decode("utf-8", "replace")
        if ctype == "text/plain":
            return text.strip()
        if ctype == "text/html" and not html_fallback:
            html_fallback = text
    if html_fallback:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_fallback)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;?", " ", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&amp;", "&", text)
        return re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"[ \t]{2,}", " ", text)).strip()
    return ""


def _attachments(msg: Message) -> list[dict[str, Any]]:
    out = []
    if not msg.is_multipart():
        return out
    for part in msg.walk():
        fn = part.get_filename()
        if not fn:
            continue
        payload = part.get_payload(decode=True) or b""
        out.append({"filename": _decode_header(fn), "content_type": part.get_content_type(),
                    "size": len(payload)})
    return out


def _summarize(uid: str, msg: Message, *, with_body: bool) -> dict[str, Any]:
    item: dict[str, Any] = {
        "uid": uid,
        "subject": _decode_header(msg.get("Subject")),
        "from": _decode_header(msg.get("From")),
        "to": _decode_header(msg.get("To")),
        "date": _decode_header(msg.get("Date")),
    }
    cc = _decode_header(msg.get("Cc"))
    if cc:
        item["cc"] = cc
    atts = _attachments(msg)
    if atts:
        item["attachments"] = atts
    if with_body:
        body = _body_text(msg)
        if len(body) > MAX_BODY_CHARS:
            item["body"] = body[:MAX_BODY_CHARS]
            item["body_truncated"] = {"returned": MAX_BODY_CHARS, "total": len(body)}
        else:
            item["body"] = body
    return item


# ── IMAP 检索 ────────────────────────────────────────────────────────────

def _select(conn: imaplib.IMAP4_SSL, folder: str) -> None:
    typ, _ = conn.select(f'"{folder}"', readonly=True)
    if typ != "OK":
        raise MailError(f"打不开邮件夹 {folder!r}。可用 list_folders 查看有哪些邮件夹。")


def _imap_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _build_criteria(*, query: str | None, sender: str | None, subject: str | None,
                    unseen: bool, days: int | None) -> list[str]:
    """构造 IMAP SEARCH 条件。中文关键词交给 CHARSET UTF-8 处理。"""
    crit: list[str] = []
    if unseen:
        crit.append("UNSEEN")
    if days:
        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        crit += ["SINCE", since]
    if sender:
        crit += ["FROM", _imap_quote(sender)]
    if subject:
        crit += ["SUBJECT", _imap_quote(subject)]
    if query:
        crit += ["TEXT", _imap_quote(query)]
    return crit or ["ALL"]


def _search(conn: imaplib.IMAP4_SSL, crit: list[str]) -> list[bytes]:
    needs_utf8 = any(ord(c) > 127 for c in "".join(crit))
    try:
        if needs_utf8:
            encoded = [c.encode("utf-8") for c in crit]
            typ, data = conn.uid("SEARCH", "CHARSET", "UTF-8", *encoded)
        else:
            typ, data = conn.uid("SEARCH", None, *crit)
    except imaplib.IMAP4.error as e:
        raise MailError(f"检索失败：{e}") from e
    if typ != "OK":
        raise MailError("检索失败，服务器拒绝了该条件")
    return data[0].split() if data and data[0] else []


def _fetch(conn: imaplib.IMAP4_SSL, uids: list[bytes], *, with_body: bool) -> list[dict[str, Any]]:
    out = []
    part = "(RFC822)" if with_body else "(BODY.PEEK[HEADER])"
    for uid in uids:
        typ, data = conn.uid("FETCH", uid, part)
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            continue
        out.append(_summarize(uid.decode(), email.message_from_bytes(data[0][1]),
                              with_body=with_body))
    return out


# ── 工具实现 ─────────────────────────────────────────────────────────────

def list_folders() -> dict[str, Any]:
    conn = _connect()
    try:
        typ, data = conn.list()
        if typ != "OK":
            raise MailError("无法列出邮件夹")
        folders = []
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
            m = re.match(r'\(([^)]*)\)\s+"([^"]*)"\s+"?([^"]*)"?$', line)
            if m:
                folders.append({"name": m.group(3), "flags": m.group(1).split()})
        return {"success": True, "data": folders}
    finally:
        conn.logout()


def search_emails(*, folder: str = "INBOX", query: str | None = None, sender: str | None = None,
                  subject: str | None = None, unseen: bool = False, days: int | None = None,
                  limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), MAX_FETCH))
    conn = _connect()
    try:
        _select(conn, folder)
        uids = _search(conn, _build_criteria(query=query, sender=sender, subject=subject,
                                             unseen=unseen, days=days))
        total = len(uids)
        picked = uids[-limit:][::-1]   # 最新的在前
        items = _fetch(conn, picked, with_body=False)
        out: dict[str, Any] = {"success": True, "data": items, "total_matched": total}
        if total > limit:
            out["truncated"] = {"returned": len(items), "total": total}
        return out
    finally:
        conn.logout()


def read_email(*, uid: str, folder: str = "INBOX") -> dict[str, Any]:
    conn = _connect()
    try:
        _select(conn, folder)
        items = _fetch(conn, [str(uid).encode()], with_body=True)
        if not items:
            return {"success": False, "error": f"邮件夹 {folder} 中找不到 uid={uid} 的邮件"}
        return {"success": True, "data": items[0]}
    finally:
        conn.logout()


def send_email(*, to: str, subject: str, body: str, cc: str | None = None) -> dict[str, Any]:
    import smtplib
    from email.mime.text import MIMEText

    host = os.environ.get("MAIL_SMTP_HOST", "").strip()
    if not host:
        return {"success": False, "error": "未配置 MAIL_SMTP_HOST，发信功能不可用。"}
    _, _, user, pwd = _require_env()
    try:
        port = int(os.environ.get("MAIL_SMTP_PORT") or 465)
    except ValueError:
        port = 465

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = email.header.Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    recipients = [a for a in re.split(r"[,;]\s*", to) if a]
    if cc:
        recipients += [a for a in re.split(r"[,;]\s*", cc) if a]

    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, pwd)
            s.sendmail(user, recipients, msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        return {"success": False, "error": f"SMTP 认证失败：{e}。请确认使用的是授权码。"}
    except (smtplib.SMTPException, OSError) as e:
        return {"success": False, "error": f"发信失败：{type(e).__name__}: {e}"}
    return {"success": True, "data": {"sent_to": recipients, "subject": subject}}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_folders",
        "description": "列出邮箱中的所有邮件夹（收件箱、已发送、垃圾邮件等）。",
        "read_only": True,
        "handler": list_folders,
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_emails",
        "description": "搜索邮件，返回摘要列表（不含正文），按时间从新到旧。可按发件人、主题、"
                       "关键词、未读状态和最近天数过滤。",
        "read_only": True,
        "handler": search_emails,
        "schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "邮件夹名，默认 INBOX"},
                "query": {"type": "string", "description": "全文关键词（匹配主题与正文）"},
                "sender": {"type": "string", "description": "发件人邮箱或名称片段"},
                "subject": {"type": "string", "description": "主题关键词"},
                "unseen": {"type": "boolean", "description": "只看未读邮件"},
                "days": {"type": "integer", "description": "只看最近 N 天的邮件"},
                "limit": {"type": "integer", "description": "返回条数，1-50，默认 20"},
            },
        },
    },
    {
        "name": "read_email",
        "description": "读取单封邮件的完整内容，含正文与附件清单。uid 来自 search_emails。",
        "read_only": True,
        "handler": read_email,
        "schema": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "邮件 UID，来自 search_emails 的结果"},
                "folder": {"type": "string", "description": "邮件夹名，默认 INBOX"},
            },
            "required": ["uid"],
        },
    },
    {
        "name": "send_email",
        "description": "发送一封纯文本邮件。这会真实投递邮件给收件人，发出后无法撤回。",
        "read_only": False,
        "handler": send_email,
        "schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "收件人邮箱，多个用逗号分隔"},
                "subject": {"type": "string", "description": "邮件主题"},
                "body": {"type": "string", "description": "邮件正文（纯文本）"},
                "cc": {"type": "string", "description": "抄送邮箱，多个用逗号分隔"},
            },
            "required": ["to", "subject", "body"],
        },
    },
]

SERVER_NAME = "imap_mail"
DISPLAY_NAME = "邮箱（IMAP/SMTP）"
DESCRIPTION = "收发、搜索和整理邮件，支持 QQ 邮箱、网易邮箱及任意 IMAP 邮箱。"
DESCRIPTION_EN = 'Read, search and send email over IMAP/SMTP — works with QQ Mail, NetEase Mail and any IMAP mailbox.'
REQUIRED_ENV = ["MAIL_IMAP_HOST", "MAIL_USERNAME", "MAIL_PASSWORD"]
OPTIONAL_ENV = ["MAIL_IMAP_PORT", "MAIL_SMTP_HOST", "MAIL_SMTP_PORT"]
