"""引擎单测。不发真实网络请求 —— httpx 被替换成可控的假响应。

    cd servers && python -m pytest tests -q
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from totalclaw_mcp_servers.engine import token_exchange as tx_mod  # noqa: E402
from totalclaw_mcp_servers.engine.client import build_request, call_tool  # noqa: E402
from totalclaw_mcp_servers.engine.render import (  # noqa: E402
    MissingValue, clip, pick_path, render_path, render_value,
)
from totalclaw_mcp_servers.engine.spec import (  # noqa: E402
    PackError, list_packs, load_pack, parse_pack,
)

MINIMAL = {
    "name": "demo",
    "display_name": "Demo",
    "base_url": "https://example.com",
    "tools": [{
        "name": "get_thing",
        "description": "取一个东西",
        "method": "GET",
        "path": "/things/{id}",
        "params": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
    }],
}


# ── 模板渲染 ─────────────────────────────────────────────────────────────

def test_whole_string_placeholder_keeps_type():
    """整串占位符必须保留原始类型，否则 per_page=5 会变成字符串 "5"。"""
    out = render_value({"n": "{count}", "b": "{flag}", "s": "x{count}"}, {"count": 5, "flag": True})
    assert out == {"n": 5, "b": True, "s": "x5"}


def test_missing_optional_is_dropped_not_blank():
    """缺失的可选参数应整项丢弃 —— 空串对多数 API 等于「显式传空」，语义不同。"""
    assert render_value({"q": "{kw}", "page": "{p}"}, {"kw": "x"}) == {"q": "x"}


def test_missing_path_param_raises():
    with pytest.raises(MissingValue):
        render_path("/repos/{owner}/{repo}", {"owner": "a"})


def test_path_params_are_url_encoded():
    assert render_path("/f/{path}", {"path": "a b/c"}) == "/f/a%20b%2Fc"


def test_env_placeholder(monkeypatch):
    monkeypatch.setenv("DEMO_REGION", "cn")
    assert render_value("region-${DEMO_REGION}", {}) == "region-cn"


def test_pick_path_falls_back_to_whole_body():
    """路径不存在时返回整体 —— 宁可多给，也不静默返回空。"""
    assert pick_path({"a": {"b": 1}}, "a.b") == 1
    assert pick_path({"a": 1}, "x.y") == {"a": 1}
    assert pick_path({"r": [{"n": 1}]}, "r.0.n") == 1


def test_clip_items_and_chars():
    data, note = clip([1, 2, 3, 4], 2, 16000)
    assert data == [1, 2] and note["truncated_items"]["total"] == 4
    data, note = clip({"s": "x" * 100}, None, 50)
    assert "truncated_chars" in note


# ── pack 校验 ────────────────────────────────────────────────────────────

def test_parse_minimal_pack():
    p = parse_pack(MINIMAL)
    assert p.name == "demo" and len(p.tools) == 1 and p.tools[0].read_only is True


def test_rejects_plain_http_base_url():
    bad = {**MINIMAL, "base_url": "http://example.com"}
    with pytest.raises(PackError, match="https"):
        parse_pack(bad)


def test_allows_loopback_http():
    parse_pack({**MINIMAL, "base_url": "http://127.0.0.1:8000"})


def test_rejects_duplicate_tool_names():
    bad = {**MINIMAL, "tools": MINIMAL["tools"] * 2}
    with pytest.raises(PackError, match="重复"):
        parse_pack(bad)


def test_rejects_bad_tool_name():
    bad = {**MINIMAL, "tools": [{**MINIMAL["tools"][0], "name": "Get-Thing"}]}
    with pytest.raises(PackError):
        parse_pack(bad)


def test_auth_requires_env_not_literal_secret():
    """凭据只能来自环境变量 —— 不允许把密钥写死在 pack 里。"""
    with pytest.raises(PackError, match="env"):
        parse_pack({**MINIMAL, "auth": {"type": "bearer"}})


def test_write_method_defaults_to_not_read_only():
    p = parse_pack({**MINIMAL, "tools": [{
        "name": "make", "description": "d", "method": "POST", "path": "/x"}]})
    assert p.tools[0].read_only is False


def test_all_shipped_packs_are_valid():
    names = list_packs()
    assert names, "packs 目录不应为空"
    for n in names:
        load_pack(n)


def test_shipped_packs_have_descriptions_and_no_hardcoded_secrets():
    for n in list_packs():
        p = load_pack(n)
        assert p.description, f"{n} 缺 description"
        for t in p.tools:
            assert len(t.description) > 5, f"{n}.{t.name} 描述太短"
        blob = json.dumps([t.query for t in p.tools] + [t.headers for t in p.tools])
        for marker in ("ghp_", "sk-", "Bearer ey"):
            assert marker not in blob, f"{n} 疑似写死了凭据"


# ── 请求构造与鉴权 ────────────────────────────────────────────────────────

def test_bearer_auth_injected(monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "secret123")
    p = parse_pack({**MINIMAL, "auth": {"type": "bearer", "env": "DEMO_KEY"}})
    req = build_request(p, p.tools[0], {"id": "1"})
    assert req["headers"]["Authorization"] == "Bearer secret123"


def test_query_auth_injected(monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "k1")
    p = parse_pack({**MINIMAL, "auth": {"type": "query", "name": "key", "env": "DEMO_KEY"}})
    req = build_request(p, p.tools[0], {"id": "1"})
    assert req["params"]["key"] == "k1"


def test_missing_credentials_reported_before_request(monkeypatch):
    monkeypatch.delenv("DEMO_KEY", raising=False)
    p = parse_pack({**MINIMAL, "auth": {"type": "bearer", "env": "DEMO_KEY"}})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is False and "DEMO_KEY" in r["error"]


# ── 响应处理 ─────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status=200, payload=None, text=None, ctype="application/json"):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.headers = {"content-type": ctype}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture
def fake_http(monkeypatch):
    import httpx

    box = {"resp": _Resp(), "seen": []}

    def fake(self, method, url, **kw):
        box["seen"].append({"method": method, "url": str(url), **kw})
        r = box["resp"]
        return r(method, url) if callable(r) else r

    monkeypatch.setattr(httpx.Client, "request", fake)
    return box


def test_success_path(fake_http):
    fake_http["resp"] = _Resp(payload={"id": "1", "name": "thing"})
    p = parse_pack(MINIMAL)
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] and r["data"]["name"] == "thing"


def test_http_error_is_structured(fake_http):
    fake_http["resp"] = _Resp(status=403, payload={"message": "forbidden"})
    p = parse_pack(MINIMAL)
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is False and r["status"] == 403


def test_business_error_code_detected(fake_http):
    """HTTP 200 + errcode!=0 必须判为失败 —— 国内 API 的常见形状。"""
    fake_http["resp"] = _Resp(payload={"errcode": 40013, "errmsg": "invalid corpid"})
    p = parse_pack({**MINIMAL, "response": {
        "error_field": "errcode", "ok_value": 0, "message_field": "errmsg"}})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is False and r["code"] == 40013 and "invalid corpid" in r["error"]


def test_graphql_style_error_not_duplicated(fake_http):
    """error_field 与 message_field 同源时（GraphQL errors[0].message），别把同一句话说两遍。"""
    fake_http["resp"] = _Resp(payload={"errors": [{"message": "Authentication required"}]})
    p = parse_pack({**MINIMAL, "response": {
        "error_field": "errors.0.message", "ok_value": "__never__",
        "message_field": "errors.0.message"}})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is False
    assert r["error"].count("Authentication required") == 1


def test_business_ok_code_passes(fake_http):
    fake_http["resp"] = _Resp(payload={"errcode": 0, "data": [1, 2]})
    p = parse_pack({**MINIMAL, "response": {"error_field": "errcode", "ok_value": 0}})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is True


def test_response_without_error_field_is_not_failed(fake_http):
    """响应里没有该字段时不能误判为失败。"""
    fake_http["resp"] = _Resp(payload={"data": "ok"})
    p = parse_pack({**MINIMAL, "response": {"error_field": "errcode", "ok_value": 0}})
    assert call_tool(p, p.tools[0], {"id": "1"})["success"] is True


def test_non_json_body_wrapped(fake_http):
    fake_http["resp"] = _Resp(text="plain text", ctype="text/plain")
    p = parse_pack(MINIMAL)
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] and r["data"]["_raw"] == "plain text"


def test_secrets_redacted_in_error(fake_http, monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "supersecretvalue")
    fake_http["resp"] = _Resp(status=500, text="failed for supersecretvalue", ctype="text/plain")
    p = parse_pack({**MINIMAL, "auth": {"type": "bearer", "env": "DEMO_KEY"}})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert "supersecretvalue" not in json.dumps(r)


# ── 令牌交换 ─────────────────────────────────────────────────────────────

def test_token_exchange_caches(fake_http, monkeypatch):
    monkeypatch.setenv("TX_ID", "id1")
    monkeypatch.setenv("TX_SECRET", "sec1")
    tx_mod._CACHE.clear()
    calls = {"n": 0}

    def responder(method, url):
        if "gettoken" in str(url):
            calls["n"] += 1
            return _Resp(payload={"access_token": "TOKEN1", "expires_in": 7200})
        return _Resp(payload={"ok": True})

    fake_http["resp"] = responder
    p = parse_pack({**MINIMAL, "auth": {
        "type": "token_exchange",
        "token_url": "https://example.com/gettoken",
        "token_query": {"id": "${TX_ID}", "secret": "${TX_SECRET}"},
        "token_pick": "access_token", "expires_pick": "expires_in",
        "place": "query", "name": "access_token",
        "requires_env": ["TX_ID", "TX_SECRET"],
    }})
    assert call_tool(p, p.tools[0], {"id": "1"})["success"]
    assert call_tool(p, p.tools[0], {"id": "1"})["success"]
    assert calls["n"] == 1, "第二次调用应命中令牌缓存"


def test_token_exchange_missing_env_reported(monkeypatch):
    monkeypatch.delenv("TX_ID", raising=False)
    monkeypatch.delenv("TX_SECRET", raising=False)
    tx_mod._CACHE.clear()
    p = parse_pack({**MINIMAL, "auth": {
        "type": "token_exchange", "token_url": "https://example.com/gettoken",
        "token_pick": "access_token", "requires_env": ["TX_ID", "TX_SECRET"],
    }})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is False and "TX_ID" in r["error"]


def test_token_exchange_requires_env_declared():
    with pytest.raises(PackError, match="requires_env"):
        parse_pack({**MINIMAL, "auth": {
            "type": "token_exchange", "token_url": "https://example.com/t",
            "token_pick": "access_token"}})


# ── 签名鉴权 ─────────────────────────────────────────────────────────────

def test_signature_md5_matches_manual(monkeypatch):
    """MD5(key+timestamp+secret) 大写 —— 企查查这类签名 API 的通用形态。"""
    import hashlib

    monkeypatch.setenv("SIG_KEY", "appkey123")
    monkeypatch.setenv("SIG_SECRET", "secret456")
    p = parse_pack({**MINIMAL, "auth": {
        "type": "signature", "algorithm": "md5",
        "parts": ["${SIG_KEY}", "{timestamp}", "${SIG_SECRET}"], "uppercase": True,
        "inject": {"headers": {"Token": "{signature}", "Timespan": "{timestamp}"},
                   "query": {"key": "${SIG_KEY}"}},
        "requires_env": ["SIG_KEY", "SIG_SECRET"]}})
    req = build_request(p, p.tools[0], {"id": "1"})
    ts = req["headers"]["Timespan"]
    expect = hashlib.md5(f"appkey123{ts}secret456".encode()).hexdigest().upper()
    assert req["headers"]["Token"] == expect
    assert req["params"]["key"] == "appkey123"


def test_signature_hmac_sha256(monkeypatch):
    import hashlib
    import hmac

    monkeypatch.setenv("SIG_ID", "id1")
    monkeypatch.setenv("SIG_SECRET", "s3cr3t")
    p = parse_pack({**MINIMAL, "auth": {
        "type": "signature", "algorithm": "hmac_sha256",
        "parts": ["${SIG_ID}", "{timestamp}"], "hmac_key": "${SIG_SECRET}", "uppercase": False,
        "inject": {"headers": {"X-Sign": "{signature}", "X-Ts": "{timestamp}"}},
        "requires_env": ["SIG_ID", "SIG_SECRET"]}})
    req = build_request(p, p.tools[0], {"id": "1"})
    ts = req["headers"]["X-Ts"]
    expect = hmac.new(b"s3cr3t", f"id1{ts}".encode(), hashlib.sha256).hexdigest()
    assert req["headers"]["X-Sign"] == expect


def test_signature_missing_env_reported(monkeypatch):
    monkeypatch.delenv("SIG_KEY", raising=False)
    monkeypatch.delenv("SIG_SECRET", raising=False)
    p = parse_pack({**MINIMAL, "auth": {
        "type": "signature", "parts": ["${SIG_KEY}"],
        "inject": {"headers": {"Token": "{signature}"}},
        "requires_env": ["SIG_KEY", "SIG_SECRET"]}})
    r = call_tool(p, p.tools[0], {"id": "1"})
    assert r["success"] is False and "SIG_KEY" in r["error"]


def test_signature_requires_inject():
    with pytest.raises(PackError, match="inject"):
        parse_pack({**MINIMAL, "auth": {
            "type": "signature", "parts": ["${A}"], "requires_env": ["A"]}})


# ── 腾讯云 TC3 签名 ───────────────────────────────────────────────────────

def test_tc3_signature_matches_independent_recompute(monkeypatch):
    """独立按官方四步复算一遍，确认实现无误 —— 签名错了上游只会回 AuthFailure，很难查。"""
    import hashlib
    import hmac
    import json as _json
    import time

    monkeypatch.setenv("TC_ID", "AKIDtest")
    monkeypatch.setenv("TC_KEY", "skTest123")
    p = parse_pack({**MINIMAL, "base_url": "https://tcb.tencentcloudapi.com",
                    "auth": {"type": "tencent_cloud", "service": "tcb", "version": "2018-06-08",
                             "secret_id_env": "TC_ID", "secret_key_env": "TC_KEY",
                             "region": "ap-shanghai"},
                    "tools": [{"name": "act", "description": "d", "method": "POST", "path": "/",
                               "headers": {"X-TC-Action": "DescribeEnvs"},
                               "body": {"EnvId": "{env_id}"},
                               "params": {"type": "object",
                                          "properties": {"env_id": {"type": "string"}}}}]})
    req = build_request(p, p.tools[0], {"env_id": "prod-1"})
    h = req["headers"]
    body = _json.dumps(req["json"], ensure_ascii=False, separators=(",", ":"))
    ts = h["X-TC-Timestamp"]
    date = time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
    ch = ("content-type:application/json; charset=utf-8\n"
          "host:tcb.tencentcloudapi.com\nx-tc-action:describeenvs\n")
    cr = "\n".join(["POST", "/", "", ch, "content-type;host;x-tc-action",
                    hashlib.sha256(body.encode()).hexdigest()])
    sts = "\n".join(["TC3-HMAC-SHA256", ts, f"{date}/tcb/tc3_request",
                     hashlib.sha256(cr.encode()).hexdigest()])
    k = hmac.new(b"TC3skTest123", date.encode(), hashlib.sha256).digest()
    k = hmac.new(k, b"tcb", hashlib.sha256).digest()
    k = hmac.new(k, b"tc3_request", hashlib.sha256).digest()
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    assert f"Signature={sig}" in h["Authorization"]
    assert h["X-TC-Version"] == "2018-06-08" and h["X-TC-Region"] == "ap-shanghai"


def test_tc3_missing_action_is_reported(monkeypatch):
    monkeypatch.setenv("TC_ID", "a"), monkeypatch.setenv("TC_KEY", "b")
    p = parse_pack({**MINIMAL, "base_url": "https://tcb.tencentcloudapi.com",
                    "auth": {"type": "tencent_cloud", "service": "tcb", "version": "2018-06-08",
                             "secret_id_env": "TC_ID", "secret_key_env": "TC_KEY"},
                    "tools": [{"name": "act", "description": "d", "method": "POST", "path": "/"}]})
    r = call_tool(p, p.tools[0], {})
    assert r["success"] is False and "X-TC-Action" in r["error"]


def test_tc3_requires_service_and_version():
    with pytest.raises(PackError, match="version"):
        parse_pack({**MINIMAL, "auth": {"type": "tencent_cloud", "service": "tcb",
                                        "secret_id_env": "A", "secret_key_env": "B"}})


# ── 原生服务器 ───────────────────────────────────────────────────────────

def test_native_modules_expose_contract():
    from totalclaw_mcp_servers import native

    names = native.list_native()
    assert names
    for n in names:
        mod = native.load_native(n)
        assert mod.SERVER_NAME and mod.DISPLAY_NAME and mod.DESCRIPTION
        for t in mod.TOOLS:
            assert {"name", "description", "handler", "schema"} <= set(t)
            assert callable(t["handler"])


def test_native_handler_errors_are_returned_not_raised(monkeypatch):
    from totalclaw_mcp_servers.native import imap_mail

    for var in ("MAIL_IMAP_HOST", "MAIL_USERNAME", "MAIL_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(imap_mail.MailError):
        imap_mail.list_folders()
    # 装配层负责兜住并转成 {"success": False}
    assert imap_mail.MailError.clean is True


# ── 网页抓取（原生） ──────────────────────────────────────────────────────

def test_web_blocks_private_and_non_http(monkeypatch):
    """默认拒绝内网与非 http(s)，避免被当成打内网的跳板。"""
    from totalclaw_mcp_servers.native.web import WebError, _check_url

    monkeypatch.delenv("TOTALCLAW_MCP_WEB_ALLOW_PRIVATE", raising=False)
    for bad in ("http://127.0.0.1:8000", "http://192.168.1.1/x", "file:///etc/passwd"):
        with pytest.raises(WebError):
            _check_url(bad)


def test_web_allow_private_escape_hatch(monkeypatch):
    """代理环境（Clash 把公网域名解析到保留段）需要能关掉校验。"""
    from totalclaw_mcp_servers.native.web import _check_url

    monkeypatch.setenv("TOTALCLAW_MCP_WEB_ALLOW_PRIVATE", "1")
    assert _check_url("http://127.0.0.1:8000").startswith("http://")


def test_web_html_extraction_drops_script_and_style():
    from totalclaw_mcp_servers.native.web import _Extractor

    ex = _Extractor()
    ex.feed("<html><head><title>标题</title><style>a{color:red}</style></head>"
            "<body><script>var x=1</script><p>正文一</p><p>正文二</p>"
            '<a href="/x">链接</a></body></html>')
    assert ex.title == "标题"
    text = ex.text()
    assert "正文一" in text and "正文二" in text
    assert "color:red" not in text and "var x" not in text
    assert ex.links == [("链接", "/x")]


def test_web_fetch_many_rejects_oversized_batch():
    from totalclaw_mcp_servers.native.web import fetch_many

    r = fetch_many(urls=[f"https://e{i}.com" for i in range(11)])
    assert r["success"] is False and "最多 10" in r["error"]
